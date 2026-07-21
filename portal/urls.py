from django.urls import path
from . import views

urlpatterns = [
    # Student
    path('', views.student_login, name='student_login'),
    path('register/', views.student_register, name='student_register'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('logout/', views.student_logout, name='logout'),

    # Webhook
    path('api/webhook/google-forms/', views.google_form_webhook, name='google_form_webhook'),

    # Admin
    path('hod-secure-portal-auth/', views.admin_login, name='admin_login'),
    path('hod-secure-portal-auth/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('hod-secure-portal-auth/logout/', views.admin_logout, name='admin_logout'),
    path('hod-secure-portal-auth/process-all/', views.process_all, name='process_all'),
    path('hod-secure-portal-auth/delete/<str:ug_number>/', views.delete_student, name='delete_student'),
    path('hod-secure-portal-auth/impersonate/<str:ug_number>/', views.impersonate_student, name='impersonate_student'),
    path('hod-secure-portal-auth/reset-password/<str:ug_number>/', views.hod_reset_student_password, name='hod_reset_student_password'),
    path('hod-secure-portal-auth/staff/', views.staff_management, name='staff_management'),
    path('hod-secure-portal-auth/staff/delete/<int:user_id>/', views.delete_staff, name='delete_staff'),
]
