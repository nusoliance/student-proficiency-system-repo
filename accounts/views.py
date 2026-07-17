from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import SignUpForm


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data.get('role')
            user.profile.role = role
            if role == 'student':
                user.profile.mode = form.cleaned_data.get('mode')
            user.profile.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})
