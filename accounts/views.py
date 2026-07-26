from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import make_password
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .forms import SignUpForm
from .models import Profile
from avatar.models import Skill, StudentSkill, Course


def _create_user_from_data(username, email, password_hash, role, mode, course, school, school_id, flagged):
    user = User(username=username, email=email,
                password=password_hash, is_active=False)
    user.save()
    user.profile.role = role
    if role == 'student':
        user.profile.mode = mode
        user.profile.course = course
        user.profile.school = school or ''
        user.profile.school_id = school_id or ''
        user.profile.under_evaluation = flagged
        user.profile.save()
        if course:
            skills_to_assign = Skill.objects.filter(
                category='general') | Skill.objects.filter(course=course)
        else:
            skills_to_assign = Skill.objects.filter(category='general')
        for skill in skills_to_assign:
            StudentSkill.objects.get_or_create(student=user, skill=skill)
    else:
        user.profile.school = school or ''
        user.profile.save()
    return user


def _send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(f'/accounts/verify/{uid}/{token}/')
    subject = 'Verify your Student Proficiency System account'
    message = render_to_string(
        'accounts/verification_email.txt', {'user': user, 'verify_url': verify_url})
    send_mail(subject, message, None, [user.email])


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            mode = form.cleaned_data.get('mode')
            school = form.cleaned_data.get('school')
            school_id = form.cleaned_data.get('school_id')
            course = form.cleaned_data.get('course')

            if role == 'student' and mode == 'professional' and school == 'citu' and school_id:
                existing = Profile.objects.filter(
                    school='citu', school_id=school_id).exists()
                if existing:
                    request.session['pending_signup'] = {
                        'username': form.cleaned_data['username'],
                        'email': form.cleaned_data['email'],
                        'password_hash': make_password(form.cleaned_data['password1']),
                        'role': role,
                        'mode': mode,
                        'course_id': course.id if course else None,
                        'school': school,
                        'school_id': school_id,
                    }
                    return redirect('confirm_school_id')

            user = _create_user_from_data(
                username=form.cleaned_data['username'], email=form.cleaned_data['email'],
                password_hash=make_password(form.cleaned_data['password1']),
                role=role, mode=mode, course=course,
                school=school, school_id=school_id, flagged=False,
            )
            _send_verification_email(request, user)
            return render(request, 'accounts/check_email.html', {'email': user.email})
    else:
        initial = request.session.pop('prefill_signup', {})
        form = SignUpForm(initial=initial)
    return render(request, 'accounts/signup.html', {'form': form})


def confirm_school_id(request):
    pending = request.session.get('pending_signup')
    if not pending:
        return redirect('signup')

    if request.method == 'POST':
        choice = request.POST.get('choice')
        if choice == 'yes':
            if User.objects.filter(username=pending['username']).exists():
                del request.session['pending_signup']
                return render(request, 'accounts/signup_conflict.html', {
                    'reason': 'username',
                })
            if User.objects.filter(email=pending['email']).exists():
                del request.session['pending_signup']
                return render(request, 'accounts/signup_conflict.html', {
                    'reason': 'email',
                })
            course = Course.objects.filter(
                id=pending['course_id']).first() if pending['course_id'] else None
            user = _create_user_from_data(
                username=pending['username'], email=pending['email'],
                password_hash=pending['password_hash'],
                role=pending['role'], mode=pending['mode'], course=course,
                school=pending['school'], school_id=pending['school_id'], flagged=True,
            )
            Profile.objects.filter(school='citu', school_id=pending['school_id']).exclude(
                user=user).update(under_evaluation=True)
            del request.session['pending_signup']
            _send_verification_email(request, user)
            return render(request, 'accounts/check_email.html', {'email': user.email})
        else:
            request.session['prefill_signup'] = {
                'username': pending['username'],
                'email': pending['email'],
                'role': pending['role'],
                'mode': pending['mode'],
                'course': pending['course_id'],
                'school': pending['school'],
            }
            del request.session['pending_signup']
            return redirect('signup')

    return render(request, 'accounts/confirm_school_id.html', {'school_id': pending['school_id']})


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
