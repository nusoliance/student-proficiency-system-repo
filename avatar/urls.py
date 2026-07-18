from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_skills, name='my_skills'),
]
