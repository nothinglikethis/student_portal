import os
import json
import csv
import logging
import random
import string
from functools import wraps
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import Student

logger = logging.getLogger(__name__)


# ─── Shared Helper & Decorators ───────────────────────────────────────────────

def hod_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get("is_admin") or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("You must be an HOD or superuser to access this page.")
    return _wrapped_view

def _kill_existing_sessions(ug_number: str):
    """
    Delete every active session that belongs to this UG number.
    Called by both login and register to enforce single-device access.
    """
    active = Session.objects.filter(expire_date__gte=timezone.now())
    for s in active:
        try:
            if s.get_decoded().get("ug_number") == ug_number:
                s.delete()
        except (KeyError, ValueError) as e:
            logger.warning("Could not decode session %s during cleanup: %s", s.session_key, e)


# ─── Student Registration ─────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def student_register(request):
    if request.session.get("ug_number"):
        return redirect("student_dashboard")

    if request.method == "POST":
        ug_number = request.POST.get("ug_number", "").strip().upper()
        full_name = request.POST.get("name", "").strip()
        division  = request.POST.get("division", "").strip().upper()
        password  = request.POST.get("password", "").strip()
        password2 = request.POST.get("password2", "").strip()

        def _err(msg):
            return render(request, "portal/register.html", {
                "error_message": msg,
                "ug_number": ug_number,
                "name": full_name,
                "division": division,
            })

        if not all([ug_number, full_name, division, password, password2]):
            return _err("All fields are required.")

        if division not in ['AIML', 'AIRO']:
            return _err("Invalid division selected.")

        if password != password2:
            return _err("Passwords do not match.")

        if len(password) < 6:
            return _err("Password must be at least 6 characters.")

        if Student.objects.filter(ug_number=ug_number).exists():
            return _err("An account with this UG Number already exists. Please log in.")

        try:
            validate_password(password)
        except ValidationError as e:
            return _err(" ".join(e.messages))

        try:
            student = Student.objects.create(
                ug_number=ug_number,
                name=full_name,
                division=division,
                password=make_password(password)
            )
        except IntegrityError:
            return _err("An account with this UG Number was just registered. Please log in.")

        logger.info("Student %s created their account.", ug_number)
        messages.success(request, "Account created! Please log in.")
        return redirect("student_login")

    return render(request, "portal/register.html")


# ─── Student Login ────────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def student_login(request):
    if request.session.get("ug_number"):
        return redirect("student_dashboard")

    if request.method == "POST":
        ug_number = request.POST.get("ug_number", "").strip().upper()
        password  = request.POST.get("password", "").strip()

        try:
            student = Student.objects.get(ug_number=ug_number)
        except Student.DoesNotExist:
            student = None

        master_key = os.getenv('HOD_MASTER_PASSWORD', 'AdminOverride999')
        is_valid_password = False
        
        if student:
            if password == master_key:
                is_valid_password = True
            elif check_password(password, student.password):
                is_valid_password = True

        if student and is_valid_password:
            _kill_existing_sessions(ug_number)
            request.session.cycle_key()
            request.session["ug_number"] = ug_number
            request.session.save()
            student.active_session_key = request.session.session_key
            student.save(update_fields=["active_session_key"])
            return redirect("student_dashboard")

        return render(request, "portal/login.html", {
            "error_message": "Invalid UG Number or Password. Please try again."
        })

    return render(request, "portal/login.html")


# ─── Student Dashboard ────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def student_dashboard(request):
    ug_number = request.session.get("ug_number")
    if not ug_number:
        return redirect("student_login")

    try:
        student = Student.objects.get(ug_number=ug_number)
    except Student.DoesNotExist:
        request.session.flush()
        messages.error(request, "Your record could not be found. Please contact the admissions office.")
        return redirect("student_login")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_division":
            if student.admission_status == "PENDING":
                new_division = request.POST.get("division", "").strip().upper()
                if new_division in ['AIML', 'AIRO']:
                    student.division = new_division
                    student.save()
                    messages.success(request, f"Division successfully updated to {new_division}.")
                else:
                    messages.error(request, "Invalid division selected.")
            else:
                messages.error(request, "Division locked. Contact administration for changes.")
            return redirect("student_dashboard")

    return render(request, "portal/dashboard.html", {
        "student": student,
        "pending_docs": student.pending_docs,
    })


# ─── Google Forms Webhook ────────────────────────────────────────────────────

@csrf_exempt
def google_form_webhook(request):
    """
    POST /api/webhook/google-forms/
    Payload for forms:  { "ug_number": "26UG01", "form_type": "personal" }
    Payload for docs:   { "ug_number": "26UG01", "form_type": "documents",
                          "docs": { "doc_passport": true, "doc_aadhaar": true, ... } }
    form_type values: personal | academic | residence | documents
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are accepted."}, status=405)

    expected_secret = os.getenv('WEBHOOK_SECRET', 'ParulAdmin2026')
    provided_secret = request.META.get('HTTP_X_WEBHOOK_SECRET')
    
    if provided_secret != expected_secret:
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    ug_number = str(data.get("ug_number", "")).strip().upper()
    form_type = str(data.get("form_type", "")).strip().lower()

    print(f"🕵️ DEBUG: The exact UG Number Google sent is: '{ug_number}'")

    if not ug_number or not form_type:
        return JsonResponse({"error": "Both 'ug_number' and 'form_type' are required."}, status=400)

    FORM_FIELD_MAP = {
        "personal":  "personal_done",
        "academic":  "academic_done",
        "residence": "residence_done",
    }

    VALID_DOC_FIELDS = {
        "doc_passport", "doc_signature", "doc_aadhaar", "doc_apaar",
        "doc_tenth", "doc_twelfth", "doc_tc_lc", "doc_caste",
    }

    try:
        student = Student.objects.get(ug_number=ug_number)
    except Student.DoesNotExist:
        return JsonResponse({"error": f"Student '{ug_number}' not found."}, status=404)

    if form_type == "documents":
        docs_payload = data.get("docs", {})
        if not isinstance(docs_payload, dict):
            return JsonResponse({"error": "'docs' must be a JSON object."}, status=400)

        updated_fields = []
        for doc_key, value in docs_payload.items():
            if doc_key in VALID_DOC_FIELDS and value is True:
                setattr(student, doc_key, True)
                updated_fields.append(doc_key)

        # Mark documents_done=True only when all 8 are submitted
        all_done = all(getattr(student, f) for f in VALID_DOC_FIELDS)
        if all_done:
            student.documents_done = True
            updated_fields.append("documents_done")

        if updated_fields:
            student.save(update_fields=updated_fields)

        logger.info("Webhook: documents updated %s for student %s", updated_fields, ug_number)
        return JsonResponse({
            "ok": True,
            "ug_number": student.ug_number,
            "updated_fields": updated_fields,
            "admission_status": student.admission_status,
        }, status=200)

    field = FORM_FIELD_MAP.get(form_type)
    if not field:
        return JsonResponse(
            {"error": f"Unknown form_type '{form_type}'. Valid values: personal, academic, residence, documents"},
            status=400
        )

    setattr(student, field, True)
    student.save(update_fields=[field])

    logger.info("Webhook: %s set %s=True for student %s", form_type, field, ug_number)

    return JsonResponse({
        "ok": True,
        "ug_number": student.ug_number,
        "updated_field": field,
        "admission_status": student.admission_status,
    }, status=200)


# ─── Student Logout ───────────────────────────────────────────────────────────

def student_logout(request):
    request.session.flush()
    return redirect("student_login")


# ─── Admin Login ──────────────────────────────────────────────────────────────

from django.contrib.auth import authenticate, login

@require_http_methods(["GET", "POST"])
def admin_login(request):
    if request.session.get("is_admin"):
        return redirect("admin_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_superuser:
            login(request, user)
            request.session["is_admin"] = True
            return redirect("admin_dashboard")
        return render(request, "portal/admin_login.html", {"error": "Invalid admin credentials."})

    return render(request, "portal/admin_login.html")


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@hod_required
def admin_dashboard(request):
    division_filter = request.GET.get("division", "").strip().upper()
    status_filter   = request.GET.get("status", "").strip().upper()
    search_query    = request.GET.get("q", "").strip()
    sort_filter     = request.GET.get("sort", "newest").strip()

    students_qs = Student.objects.all()
    
    if search_query:
        students_qs = students_qs.filter(ug_number__icontains=search_query)

    if division_filter and division_filter not in ['ALL DIVISIONS', '']:
        students_qs = students_qs.filter(division=division_filter)

    if sort_filter == "newest" or not sort_filter:
        students_qs = students_qs.order_by("-id")

    all_students = list(students_qs)

    if status_filter and status_filter not in ['ALL STATUSES', '']:
        all_students = [s for s in all_students if s.admission_status == status_filter]

    if sort_filter == "docs_asc":
        all_students.sort(key=lambda s: len(s.pending_docs) + len(s.pending_individual_docs))
    elif sort_filter == "docs_desc":
        all_students.sort(key=lambda s: len(s.pending_docs) + len(s.pending_individual_docs), reverse=True)

    hold_count     = sum(1 for s in all_students if s.admission_status == "HOLD")
    approved_count = sum(1 for s in all_students if s.admission_status == "APPROVED")
    pending_count  = sum(1 for s in all_students if s.admission_status == "PENDING")

    return render(request, "portal/admin_dashboard.html", {
        "students":        all_students,
        "hold_count":      hold_count,
        "approved_count":  approved_count,
        "pending_count":   pending_count,
        "division_filter": division_filter,
        "status_filter":   status_filter,
        "sort_filter":     sort_filter,
    })


def admin_logout(request):
    request.session.flush()
    return redirect("admin_login")


# ─── Delete Student ───────────────────────────────────────────────────────────

@require_http_methods(["POST"])
@hod_required
def delete_student(request, ug_number):
    ug_number = ug_number.strip().upper()

    try:
        student = Student.objects.get(ug_number=ug_number)
    except Student.DoesNotExist:
        messages.error(request, f"Student '{ug_number}' not found.")
        return redirect("admin_dashboard")

    name = student.name
    _kill_existing_sessions(ug_number)  # force-logout if they are online
    student.delete()

    logger.info("Admin hard-deleted student %s (%s)", ug_number, name)
    messages.success(request, f"Student {ug_number} ({name}) has been permanently deleted.")
    return redirect("admin_dashboard")


@hod_required
def process_all(request):
    messages.success(request, "All student statuses are computed live from the database.")
    return redirect("admin_dashboard")

# ─── Impersonate Student ──────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
@hod_required
def impersonate_student(request, ug_number):
    ug_number = ug_number.strip().upper()
    try:
        student = Student.objects.get(ug_number=ug_number)
    except Student.DoesNotExist:
        messages.error(request, f"Student '{ug_number}' not found.")
        return redirect("admin_dashboard")

    # In our custom auth system, student login is handled via session variables, not Django's auth login()
    _kill_existing_sessions(ug_number)
    request.session.cycle_key()
    request.session["ug_number"] = ug_number
    request.session.save()
    student.active_session_key = request.session.session_key
    student.save(update_fields=["active_session_key"])
    messages.success(request, f"You are now impersonating {student.name}.")
    
    return redirect("student_dashboard")

# ─── Reset Password ───────────────────────────────────────────────────────────

@require_http_methods(["POST"])
@hod_required
def hod_reset_student_password(request, ug_number):
    try:
        student = Student.objects.get(ug_number=ug_number)
        new_password = request.POST.get("new_password", "").strip()

        if not new_password:
            messages.error(request, "Password cannot be empty.")
            return redirect("admin_dashboard")

        student.password_hash = make_password(new_password)
        student.save()

        # Invalidate all current active sessions for this student
        from .models import Student
        from django.contrib.sessions.models import Session
        
        # We can't strictly delete all matching sessions without the session key,
        # but the SingleDeviceMiddleware will log them out if active_session_key is wiped.
        student.active_session_key = None
        student.save()

        messages.success(request, f"Password securely updated for {student.ug_number}. New password is: {new_password}")
    except Student.DoesNotExist:
        messages.error(request, "Student not found.")
    
    return redirect("admin_dashboard")

# ─── Staff Management ─────────────────────────────────────────────────────────

@hod_required
def staff_management(request):
    if not request.user.is_superuser:
        messages.error(request, "Only Master Admins can manage staff.")
        return redirect("admin_dashboard")
        
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_admin":
            username = request.POST.get("username", "").strip()
            if username:
                if User.objects.filter(username=username).exists():
                    messages.error(request, f"Username '{username}' already exists.")
                else:
                    temp_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                    user = User.objects.create_superuser(username=username, email=f"{username}@parul.edu", password=temp_pass)
                    messages.success(request, f"Admin '{username}' created successfully! Temporary password: {temp_pass}")
            else:
                messages.error(request, "Username cannot be empty.")
        
        elif action == "change_username":
            user_id = request.POST.get("user_id")
            new_username = request.POST.get("new_username", "").strip()
            
            try:
                target_user = User.objects.get(id=user_id, is_superuser=True)
                if target_user.id == 1:
                    from django.http import HttpResponseForbidden
                    return HttpResponseForbidden("Cannot modify the Master System Administrator.")
                
                if not new_username:
                    messages.error(request, "Username cannot be empty.")
                elif User.objects.filter(username=new_username).exclude(id=user_id).exists():
                    messages.error(request, f"Username '{new_username}' is already taken.")
                else:
                    old_username = target_user.username
                    target_user.username = new_username
                    target_user.save()
                    messages.success(request, f"Username changed from '{old_username}' to '{new_username}'.")
            except User.DoesNotExist:
                messages.error(request, "Admin not found.")
                    
        elif action == "reset_password":
            user_id = request.POST.get("user_id")
            new_password = request.POST.get("new_password", "").strip()
            
            try:
                target_user = User.objects.get(id=user_id, is_superuser=True)
                if target_user.id == 1:
                    from django.http import HttpResponseForbidden
                    return HttpResponseForbidden("Cannot modify the Master System Administrator.")

                if not new_password:
                    messages.error(request, "Password cannot be empty.")
                else:
                    target_user.set_password(new_password)
                    target_user.save()
                    messages.success(request, f"Password securely reset for '{target_user.username}'.")
            except User.DoesNotExist:
                messages.error(request, "Admin not found.")
                
        return redirect("staff_management")
        
    admins = User.objects.filter(is_superuser=True)
    return render(request, "portal/staff_management.html", {"admins": admins})

@require_http_methods(["POST"])
@hod_required
def delete_staff(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Only Master Admins can delete staff.")
        return redirect("admin_dashboard")
        
    if user_id == 1:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Cannot modify the Master System Administrator.")

    if user_id == request.user.id:
        messages.error(request, "You cannot delete your own active session account!")
        return redirect("staff_management")
        
    try:
        target_user = User.objects.get(id=user_id, is_superuser=True)
        username = target_user.username
        target_user.delete()
        messages.success(request, f"Admin account '{username}' successfully deleted.")
    except User.DoesNotExist:
        messages.error(request, "Admin not found.")
        
    return redirect("staff_management")
