from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from avatar.models import Course
from django.forms.models import construct_instance


class SignUpForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        help_text="Your full name or preferred display name.",
    )
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

    def _post_clean(self):
        opts = self._meta
        exclude = self._get_validation_exclusions()
        exclude.add('username')
        self.instance = construct_instance(
            self, self.instance, opts.fields, opts.exclude)
        try:
            self.instance.full_clean(exclude=exclude, validate_unique=False)
        except forms.ValidationError as e:
            self.add_error(None, e)
        if self._validate_unique:
            self.validate_unique()
