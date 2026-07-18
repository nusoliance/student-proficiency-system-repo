from django import forms
from .models import Subject, Topic, Activity


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'students']


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
