from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from avatar.models import Course
from django.forms.models import construct_instance
from django.core.validators import RegexValidator
from .models import Profile


school_id_validator = RegexValidator(
    regex=r'^\d{2}-\d{4}-\d{3}$', message="Format must be 11-1111-111")

middle_initial_validator = RegexValidator(
    regex=r'^[A-Za-z]\.$',
    message="Enter a single letter followed by a period, e.g. \"R.\"")


class NameForm(forms.Form):
    last_name = forms.CharField(max_length=150, label="Last Name")
    first_name = forms.CharField(max_length=150, label="First Name")
    middle_initial = forms.CharField(
        max_length=4, label="Middle Initial",
        validators=[middle_initial_validator],
        help_text='Single letter with a period, e.g. "R."')

    def clean_middle_initial(self):
        value = self.cleaned_data['middle_initial'].strip()
        if len(value) == 2:
            value = value[0].upper() + value[1]
        return value


class SignUpForm(UserCreationForm):
    username = forms.CharField(
        max_length=150, help_text="Your full name or preferred display name.")
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

    school = forms.ChoiceField(
        choices=[('', '---------')] + Profile.SCHOOL_CHOICES,
        required=False, label="School (teachers & professional students only)"
    )
    school_id = forms.CharField(
        required=False, validators=[school_id_validator],
        label="School ID (format: 11-1111-111)"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2',
                  'role', 'mode', 'course', 'school', 'school_id']

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        mode = cleaned.get('mode')
        school = cleaned.get('school')
        school_id = cleaned.get('school_id')

        is_professional_student = role == 'student' and mode == 'professional'
        is_citu_professional_student = is_professional_student and school == 'citu'
        can_pick_school = role == 'teacher' or is_professional_student

        if not can_pick_school:
            cleaned['school'] = ''
        if not is_citu_professional_student:
            cleaned['school_id'] = ''

        if is_professional_student:
            if not school:
                self.add_error('school', 'Please select your school.')
            elif school == 'citu' and not school_id:
                self.add_error('school_id', 'Please enter your school ID.')

        return cleaned

    def _post_clean(self):
        exclude = self._get_validation_exclusions()
        exclude.add('username')
        try:
            self.instance.full_clean(exclude=exclude, validate_unique=False)
        except forms.ValidationError as e:
            self.add_error(None, e)
        if self._validate_unique:
            self.validate_unique()
