from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('verify/<str:uidb64>/<str:token>/',
         views.verify_email, name='verify_email'),
    path('confirm-school-id/', views.confirm_school_id, name='confirm_school_id'),
    path('edit-name/', views.edit_name, name='edit_name'),
]
