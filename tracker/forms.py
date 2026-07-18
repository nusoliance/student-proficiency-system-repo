from django import forms
from django.contrib.auth.models import User
from avatar.models import Skill
from .models import Subject, Topic, Activity, Project, ProjectSubmission, SkillAward


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'students']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['students'].queryset = User.objects.filter(
            profile__role='student')


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['week_number', 'title']


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['title', 'deadline', 'skills']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'deadline']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = ProjectSubmission
        fields = ['content']


class SkillAwardForm(forms.ModelForm):
    class Meta:
        model = SkillAward
        fields = ['skill', 'points']

    def __init__(self, *args, **kwargs):
        student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        if student:
            skill_ids = student.skills.values_list('skill_id', flat=True)
            self.fields['skill'].queryset = Skill.objects.filter(
                id__in=skill_ids)


class ManageStudentsForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['students']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['students'].queryset = User.objects.filter(
            profile__role='student')
