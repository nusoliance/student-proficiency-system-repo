from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


class RequireStudentNameMiddleware:
    """
    Any logged-in student who hasn't filled in their Last Name / First Name
    yet (via the 'My Name' form) gets redirected there on every request,
    until they complete it. Logging out is still allowed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        static_url = '/' + settings.STATIC_URL.lstrip('/')
        media_url = '/' + settings.MEDIA_URL.lstrip('/') if settings.MEDIA_URL else None

        if (
            user is not None and user.is_authenticated
            and getattr(user, 'profile', None) is not None
            and user.profile.role == 'student'
            and (not user.first_name or not user.last_name)
            and not request.path.startswith(static_url)
            and not (media_url and request.path.startswith(media_url))
        ):
            exempt_paths = {reverse('edit_name'), reverse('logout')}
            if request.path not in exempt_paths:
                return redirect('edit_name')

        return self.get_response(request)