from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display  = ("ug_number", "name", "admission_status",
                     "personal_done", "academic_done",
                     "residence_done", "documents_done", "created_at")
    list_filter   = ("personal_done", "academic_done",
                     "residence_done", "documents_done")
    search_fields = ("ug_number", "name")
    readonly_fields = ("created_at",)
    ordering      = ("ug_number",)
