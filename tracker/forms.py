from django import forms
from django.contrib.auth.models import User
from avatar.models import Skill
from .models import Subject, Topic, LessonPlan, Activity, Project, ProjectSubmission, SkillAward, ActivityCompletion, Assignment, AssignmentCompletion, PersonalTask, TopicDocument, TopicImage, Quiz, QuizSkillWeight, QuizCompletion, QuizSkillAward, Exam, ExamSkillWeight, ExamCompletion, ExamSkillAward, DAY_CHOICES
from django.db.models import Sum

class SubjectScheduleFieldsMixin(forms.Form):
    subject_type = forms.ChoiceField(
        choices=[('', '— Select —')] + Subject.SUBJECT_TYPE_CHOICES,
        required=False, label='Lecture or Laboratory')
    delivery_mode = forms.ChoiceField(
        choices=[('', '— Select —')] + Subject.DELIVERY_MODE_CHOICES,
        required=False, label='Class Format')
    start_time = forms.TimeField(
        required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
    end_time = forms.TimeField(
        required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
    room = forms.CharField(required=False, max_length=100, label='Room')
    professor_name = forms.CharField(
        required=False, max_length=100, label='Teacher / Professor Name')
    days = forms.MultipleChoiceField(
        choices=DAY_CHOICES, required=False,
        widget=forms.CheckboxSelectMultiple, label='Day(s) of the week')
    onsite_days = forms.MultipleChoiceField(
        choices=DAY_CHOICES, required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Which of those days are onsite? (the rest are online)')

    def clean(self):
        cleaned_data = super().clean()
        delivery_mode = cleaned_data.get('delivery_mode')
        days = cleaned_data.get('days') or []
        onsite_days = cleaned_data.get('onsite_days') or []
        room = cleaned_data.get('room')

        if not set(onsite_days).issubset(set(days)):
            self.add_error(
                'onsite_days', 'Onsite days must also be selected as class days.')

        if delivery_mode == 'onsite' and days and not room:
            self.add_error('room', 'Room is required for onsite classes.')
        if delivery_mode == 'hybrid' and onsite_days and not room:
            self.add_error('room', 'Room is required for the onsite day(s).')

        return cleaned_data


class SubjectForm(SubjectScheduleFieldsMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = [
            'name', 'students', 'subject_type', 'delivery_mode',
            'start_time', 'end_time', 'room', 'professor_name',
        ]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        if user.profile.mode == 'personal':
            del self.fields['students']
        else:
            self.fields['students'].queryset = User.objects.filter(
                profile__role='student', profile__mode='professional')


class SubjectCustomizeForm(SubjectScheduleFieldsMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = [
            'name', 'subject_type', 'delivery_mode',
            'start_time', 'end_time', 'room', 'professor_name',
        ]


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

class TopicDocumentForm(forms.ModelForm):
    class Meta:
        model = TopicDocument
        fields = ['document']


class TopicImageForm(forms.ModelForm):
    class Meta:
        model = TopicImage
        fields = ['image']

class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['title', 'instructions', 'deadline', 'max_score', 'term',
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

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'instructions', 'deadline', 'max_score', 'term',
                  'skill_main', 'skill_secondary', 'skill_tertiary']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        relevant_skills = kwargs.pop('relevant_skills')
        super().__init__(*args, **kwargs)
        self.fields['skill_main'].queryset = relevant_skills
        self.fields['skill_secondary'].queryset = relevant_skills
        self.fields['skill_tertiary'].queryset = relevant_skills


class AssignmentCompletionForm(forms.ModelForm):
    class Meta:
        model = AssignmentCompletion
        fields = ['image', 'document']


class GradeAssignmentForm(forms.ModelForm):
    class Meta:
        model = AssignmentCompletion
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
        fields = ['title', 'no_deadline', 'deadline', 'start_time', 'end_time', 'difficulty', 'importance',
                  'skill_main', 'skill_secondary', 'skill_tertiary', 'repeat', 'notify']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }
        labels = {'start_time': 'Start time (optional)', 'end_time': 'End time (optional)'}

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
        start_time = cleaned.get('start_time')
        end_time = cleaned.get('end_time')
        repeat = cleaned.get('repeat')
        weekly_days = cleaned.get('weekly_days')

        if no_deadline:
            cleaned['deadline'] = None
        elif not deadline:
            self.add_error(
                'deadline', 'A deadline is required unless this task has no deadline.')

        if bool(start_time) != bool(end_time):
            self.add_error(
                'end_time' if start_time else 'start_time',
                'Set both a start time and an end time, or leave both blank.')
        elif start_time and end_time and end_time <= start_time:
            self.add_error(
                'end_time', 'End time must be after the start time.')

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

COMBINED_WEIGHT_FIELDS = ['activity_weight', 'quiz_weight', 'assignment_weight']
SPLIT_WEIGHT_FIELDS = [
    'midterm_activity_weight', 'final_activity_weight',
    'midterm_quiz_weight', 'final_quiz_weight',
    'midterm_assignment_weight', 'final_assignment_weight',
]
SHARED_WEIGHT_FIELDS = [
    'prelim_weight', 'midterm_weight', 'prefinal_weight', 'final_weight', 'project_weight',
]
SUBJECT_WEIGHT_FIELDS = COMBINED_WEIGHT_FIELDS + SPLIT_WEIGHT_FIELDS + SHARED_WEIGHT_FIELDS


class SubjectWeightsForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = SUBJECT_WEIGHT_FIELDS + ['at_risk_threshold']
        widgets = {
            field: forms.NumberInput(attrs={'min': 0, 'max': 100})
            for field in SUBJECT_WEIGHT_FIELDS + ['at_risk_threshold']
        }
        labels = {
            'activity_weight': 'Activities %',
            'quiz_weight': 'Quizzes %',
            'assignment_weight': 'Assignments %',
            'midterm_activity_weight': 'Midterm Activities %',
            'final_activity_weight': 'Final Activities %',
            'midterm_quiz_weight': 'Midterm Quizzes %',
            'final_quiz_weight': 'Final Quizzes %',
            'midterm_assignment_weight': 'Midterm Assignments %',
            'final_assignment_weight': 'Final Assignments %',
            'prelim_weight': 'Prelim Exam %',
            'midterm_weight': 'Midterm Exam %',
            'prefinal_weight': 'Prefinal Exam %',
            'final_weight': 'Final Exam %',
            'project_weight': 'Projects %',
            'at_risk_threshold': 'Flag students below this General Average (%)',
        }

    def __init__(self, *args, **kwargs):
        self.divide_by_semester = kwargs.pop('divide_by_semester', False)
        super().__init__(*args, **kwargs)
        if self.divide_by_semester:
            for field in COMBINED_WEIGHT_FIELDS:
                del self.fields[field]
            self.active_weight_fields = SPLIT_WEIGHT_FIELDS + SHARED_WEIGHT_FIELDS
        else:
            for field in SPLIT_WEIGHT_FIELDS:
                del self.fields[field]
            self.active_weight_fields = COMBINED_WEIGHT_FIELDS + SHARED_WEIGHT_FIELDS

    def clean(self):
        cleaned_data = super().clean()
        values = [cleaned_data.get(f) for f in self.active_weight_fields]
        if all(v is not None for v in values):
            if sum(values) != 100:
                raise forms.ValidationError(
                    'All weight percentages shown must add up to 100.')
        return cleaned_data


class QuizForm(forms.ModelForm):
    passing_percentage = forms.IntegerField(
        min_value=1, max_value=100, label="Passing Score (% of Max Score)",
        help_text="e.g. 60 means students need 60% of the max score to pass"
    )

    class Meta:
        model = Quiz
        fields = ['title', 'instructions', 'deadline', 'max_score', 'passing_percentage', 'term', 'file', 'link']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})} 


class QuizSkillWeightForm(forms.ModelForm):
    class Meta:
        model = QuizSkillWeight
        fields = ['skill', 'percentage']

    def __init__(self, *args, **kwargs):
        self.quiz = kwargs.pop('quiz')
        relevant_skills = kwargs.pop('relevant_skills')
        super().__init__(*args, **kwargs)
        already_used = self.quiz.skill_weights.values_list('skill_id', flat=True)
        self.fields['skill'].queryset = relevant_skills.exclude(id__in=already_used)

    def clean_percentage(self):
        percentage = self.cleaned_data['percentage']
        existing_total = self.quiz.skill_weights.aggregate(total=Sum('percentage'))['total'] or 0
        if existing_total + percentage > 100:
            raise forms.ValidationError(f"Total percentage can't exceed 100%. Currently at {existing_total}%.")
        return percentage


class GradeQuizForm(forms.ModelForm):
    class Meta:
        model = QuizCompletion
        fields = ['score']

    def __init__(self, *args, **kwargs):
        self.max_score = kwargs.pop('max_score')
        super().__init__(*args, **kwargs)

    def clean_score(self):
        score = self.cleaned_data['score']
        if score > self.max_score:
            raise forms.ValidationError(f"Score can't exceed the maximum of {self.max_score}.")
        return score

class ExamForm(forms.ModelForm):
    passing_percentage = forms.IntegerField(
        min_value=1, max_value=100, label="Passing Score (% of Max Score)",
        help_text="e.g. 60 means students need 60% of the max score to pass"
    )

    class Meta:
        model = Exam
        fields = ['instructions', 'deadline', 'max_score', 'passing_percentage', 'file', 'image', 'link']
        widgets = {'deadline': forms.DateInput(attrs={'type': 'date'})}


class ExamSkillWeightForm(forms.ModelForm):
    class Meta:
        model = ExamSkillWeight
        fields = ['skill', 'percentage']

    def __init__(self, *args, **kwargs):
        self.exam = kwargs.pop('exam')
        relevant_skills = kwargs.pop('relevant_skills')
        super().__init__(*args, **kwargs)
        already_used = self.exam.skill_weights.values_list('skill_id', flat=True)
        self.fields['skill'].queryset = relevant_skills.exclude(id__in=already_used)

    def clean_percentage(self):
        percentage = self.cleaned_data['percentage']
        existing_total = self.exam.skill_weights.aggregate(total=Sum('percentage'))['total'] or 0
        if existing_total + percentage > 100:
            raise forms.ValidationError(f"Total percentage can't exceed 100%. Currently at {existing_total}%.")
        return percentage


class GradeExamForm(forms.ModelForm):
    class Meta:
        model = ExamCompletion
        fields = ['score']

    def __init__(self, *args, **kwargs):
        self.max_score = kwargs.pop('max_score')
        super().__init__(*args, **kwargs)

    def clean_score(self):
        score = self.cleaned_data['score']
        if score > self.max_score:
            raise forms.ValidationError(f"Score can't exceed the maximum of {self.max_score}.")
        return score