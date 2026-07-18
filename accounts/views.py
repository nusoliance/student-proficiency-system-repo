from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import SignUpForm
from avatar.models import Skill, StudentSkill


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
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
                    skills_to_assign = Skill.objects.filter(category='broad')

                for skill in skills_to_assign:
                    StudentSkill.objects.get_or_create(
                        student=user, skill=skill)
            else:
                user.profile.save()

            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})
