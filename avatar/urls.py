from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_skills, name='my_skills'),
    path('students/', views.student_directory, name='student_directory'),
    path('students/<int:student_id>/',
         views.view_student_skills, name='view_student_skills'),
]
