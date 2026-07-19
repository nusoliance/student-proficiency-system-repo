from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static


@login_required
def home_view(request):
    return render(request, 'home.html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('tracker/', include('tracker.urls')),
    path('avatar/', include('avatar.urls')),
    path('forum/', include('forum.urls')),
    path('', home_view, name='home'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
