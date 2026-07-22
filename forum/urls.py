from django.urls import path
from . import views

urlpatterns = [
    path('', views.forum_list, name='forum_list'),
    path('<int:subject_id>/', views.forum_view, name='forum_view'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/bookmark/',
         views.toggle_bookmark, name='toggle_bookmark'),
    path('post/<int:post_id>/report/', views.report_post, name='report_post'),
    path('course/', views.course_forum_view, name='course_forum_view'),
    path('course/list/', views.course_forum_list, name='course_forum_list'),
    path('course/<int:course_id>/', views.course_forum_view,
         name='course_forum_view_detail'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('answer/<int:answer_id>/delete/',
         views.delete_answer, name='delete_answer'),
]
