from django.urls import path
from . import views

urlpatterns = [
    path('', views.subject_list, name='subject_list'),
    path('add/', views.add_subject, name='add_subject'),
    path('<int:subject_id>/', views.lesson_plan_view, name='lesson_plan_view'),
    path('<int:subject_id>/add-topic/', views.add_topic, name='add_topic'),
    path('topic/<int:topic_id>/add-activity/',
         views.add_activity, name='add_activity'),
    path('activity/<int:activity_id>/complete/',
         views.mark_complete, name='mark_complete'),
]
