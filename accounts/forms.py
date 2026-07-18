from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from avatar.models import Course


class SignUpForm(UserCreationForm):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]
    MODE_CHOICES = [
        ('personal', 'Personal'),
        ('professional', 'Professional'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    mode = forms.ChoiceField(choices=MODE_CHOICES, required=False,
                             label="Personal or Professional (students only)")
    course = forms.ModelChoiceField(
        queryset=Course.objects.all(), required=False,
        empty_label="Not in College / No Course", label="Course (students only)"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1',
                  'password2', 'role', 'mode', 'course']
