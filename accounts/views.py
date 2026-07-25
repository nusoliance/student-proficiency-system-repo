import logging

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from .forms import SignUpForm
from avatar.models import Skill, StudentSkill

logger = logging.getLogger(__name__)


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.save()

                    role = form.cleaned_data.get('role')
                    user.profile.role = role
                    if role == 'student':
                        user.profile.mode = form.cleaned_data.get('mode')
                        course = form.cleaned_data.get('course')
                        user.profile.course = course
                        user.profile.save()
                        if course:
                            skills_to_assign = Skill.objects.filter(
                                category='general') | Skill.objects.filter(course=course)
                        else:
                            skills_to_assign = Skill.objects.filter(
                                category='broad')
                        for skill in skills_to_assign:
                            StudentSkill.objects.get_or_create(
                                student=user, skill=skill)
                    else:
                        user.profile.save()

                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)
                    verify_url = request.build_absolute_uri(
                        f'/accounts/verify/{uid}/{token}/')

                    subject = 'Verify your Student Proficiency System account'
                    message = render_to_string(
                        'accounts/verification_email.txt', {'user': user, 'verify_url': verify_url})
                    # send_mail runs INSIDE the atomic block: if it raises,
                    # the whole transaction (user + profile + skills) rolls
                    # back, so the username is never left "taken" by a
                    # signup that never actually completed.
                    send_mail(subject, message, None, [user.email])
            except Exception:
                logger.exception(
                    'Signup failed while creating account or sending verification email')
                form.add_error(
                    None,
                    "We couldn't finish creating your account because the verification "
                    "email failed to send. Please try again in a few minutes."
                )
            else:
                return render(request, 'accounts/check_email.html', {'email': user.email})
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return redirect('home')
    return render(request, 'accounts/verify_invalid.html')
