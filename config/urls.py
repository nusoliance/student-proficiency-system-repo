from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home_view(request):
    return render(request, 'home.html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', home_view, name='home'),
]
