from django import forms
from django.contrib.auth.models import User
from avatar.models import Skill
from .models import Subject, Topic, LessonPlan, Activity, Project, ProjectSubmission, SkillAward, ActivityCompletion, PersonalTask


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'students']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        if user.profile.mode == 'personal':
            del self.fields['students']
        else:
            self.fields['students'].queryset = User.objects.filter(
                profile__role='student', profile__mode='professional')


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ['title', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            self.add_error(
                'end_date', 'End date must be after the start date.')
        return cleaned


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['title', 'instructions', 'deadline', 'max_score',
                  'skill_main', 'skill_secondary', 'skill_tertiary']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        relevant_skills = kwargs.pop('relevant_skills')
        super().__init__(*args, **kwargs)
        self.fields['skill_main'].queryset = relevant_skills
        self.fields['skill_secondary'].queryset = relevant_skills
        self.fields['skill_tertiary'].queryset = relevant_skills


class ActivityCompletionForm(forms.ModelForm):
    class Meta:
        model = ActivityCompletion
        fields = ['image', 'document']


class GradeActivityForm(forms.ModelForm):
    class Meta:
        model = ActivityCompletion
        fields = ['score']

    def __init__(self, *args, **kwargs):
        self.max_score = kwargs.pop('max_score')
        super().__init__(*args, **kwargs)

    def clean_score(self):
        score = self.cleaned_data['score']
        if score > self.max_score:
            raise forms.ValidationError(
                f"Score can't exceed the maximum of {self.max_score}.")
        return score


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'deadline', 'max_score']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = ProjectSubmission
        fields = ['image', 'document']


class GradeProjectForm(forms.ModelForm):
    class Meta:
        model = ProjectSubmission
        fields = ['score']

    def __init__(self, *args, **kwargs):
        self.max_score = kwargs.pop('max_score')
        super().__init__(*args, **kwargs)

    def clean_score(self):
        score = self.cleaned_data['score']
        if score > self.max_score:
            raise forms.ValidationError(
                f"Score can't exceed the maximum of {self.max_score}.")
        return score


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
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['students'].queryset = User.objects.filter(
            profile__role='student', profile__mode='professional')


class TaskActivityForm(forms.ModelForm):
    topic = forms.ModelChoiceField(queryset=Topic.objects.none())

    class Meta:
        model = Activity
        fields = ['topic', 'title', 'instructions', 'deadline',
                  'max_score', 'skill_main', 'skill_secondary', 'skill_tertiary']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        relevant_skills = kwargs.pop('relevant_skills')
        super().__init__(*args, **kwargs)
        self.fields['topic'].queryset = Topic.objects.filter(
            lesson_plan__subject__teacher=user)
        self.fields[
            'topic'].label_from_instance = lambda obj: f"{obj.lesson_plan.subject.name} — {obj.title} ({obj.start_date} to {obj.end_date})"
        self.fields['skill_main'].queryset = relevant_skills
        self.fields['skill_secondary'].queryset = relevant_skills
        self.fields['skill_tertiary'].queryset = relevant_skills


class TaskProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['subject', 'title', 'description', 'deadline', 'max_score']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.filter(teacher=user)


class PersonalTaskForm(forms.ModelForm):
    weekly_days = forms.MultipleChoiceField(
        choices=PersonalTask.WEEKDAY_CHOICES, required=False,
        widget=forms.CheckboxSelectMultiple, label="Repeat on which days"
    )

    class Meta:
        model = PersonalTask
        fields = ['title', 'no_deadline', 'deadline', 'difficulty', 'importance',
                  'skill_main', 'skill_secondary', 'skill_tertiary', 'repeat', 'notify']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        owned_skills = Skill.objects.filter(
            id__in=user.skills.values_list('skill_id', flat=True))
        self.fields['skill_main'].queryset = owned_skills
        self.fields['skill_secondary'].queryset = owned_skills
        self.fields['skill_tertiary'].queryset = owned_skills
        if self.instance and self.instance.weekly_days:
            self.fields['weekly_days'].initial = self.instance.weekly_days.split(
                ',')

    def clean(self):
        cleaned = super().clean()
        no_deadline = cleaned.get('no_deadline')
        deadline = cleaned.get('deadline')
        repeat = cleaned.get('repeat')
        weekly_days = cleaned.get('weekly_days')

        if no_deadline:
            cleaned['deadline'] = None
        elif not deadline:
            self.add_error(
                'deadline', 'A deadline is required unless this task has no deadline.')

        if repeat == 'weekly' and not weekly_days:
            self.add_error(
                'weekly_days', 'Pick at least one day for a weekly task.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.weekly_days = ','.join(
            self.cleaned_data.get('weekly_days', []))
        if commit:
            instance.save()
        return instance

class SubjectWeightsForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['activity_weight', 'project_weight', 'at_risk_threshold']
        widgets = {
            'activity_weight': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'project_weight': forms.NumberInput(attrs={'min': 0, 'max': 100}),
            'at_risk_threshold': forms.NumberInput(attrs={'min': 0, 'max': 100}),
        }
        labels = {
            'at_risk_threshold': 'Flag students below this General Average (%)',
        }

    def clean(self):
        cleaned_data = super().clean()
        activity_weight = cleaned_data.get('activity_weight')
        project_weight = cleaned_data.get('project_weight')
        if activity_weight is not None and project_weight is not None:
            if activity_weight + project_weight != 100:
                raise forms.ValidationError(
                    'Activities % and Projects % must add up to 100.')
        return cleaned_data
