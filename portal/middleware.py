from django.shortcuts import redirect
from django.contrib import messages
from portal.models import Student

class SingleDeviceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ug_number = request.session.get("ug_number")
        if ug_number:
            try:
                student = Student.objects.get(ug_number=ug_number)
                # If active_session_key exists and does not match the current session
                if student.active_session_key and request.session.session_key and student.active_session_key != request.session.session_key:
                    request.session.flush()
                    messages.error(request, "You have been logged out because your account was accessed from another device.")
                    return redirect("student_login")
            except Student.DoesNotExist:
                pass
        
        response = self.get_response(request)
        return response
