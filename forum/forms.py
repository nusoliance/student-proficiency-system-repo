from django import forms
from .models import ForumPost, Answer, Report


class ForumPostForm(forms.ModelForm):
    class Meta:
        model = ForumPost
        fields = ['text']


class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['text']


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason']
