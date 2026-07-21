from django.db import models
from django.contrib.auth.models import User
from avatar.models import Skill
from django.utils import timezone
from datetime import timedelta


class Subject(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='subjects_taught')
    students = models.ManyToManyField(
        User, related_name='subjects_enrolled', blank=True)

    def __str__(self):
        return self.name


class LessonPlan(models.Model):
    subject = models.OneToOneField(
        Subject, on_delete=models.CASCADE, related_name='lesson_plan')

    def __str__(self):
        return f"Lesson Plan for {self.subject.name}"


class Topic(models.Model):
    lesson_plan = models.ForeignKey(
        LessonPlan, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.title} ({self.start_date} – {self.end_date})"


class Activity(models.Model):
    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name='activities')
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def due_soon(self):
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    def __str__(self):
        return self.title


class ActivityCompletion(models.Model):
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='completions')
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='activity_completions')
    image = models.ImageField(
        upload_to='activity_submissions/images/', null=True, blank=True)
    document = models.FileField(
        upload_to='activity_submissions/documents/', null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('activity', 'student')

    def __str__(self):
        return f"{self.student.username} completed {self.activity.title}"


class ActivitySkillPoints(models.Model):
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='skill_points')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=10)

    class Meta:
        unique_together = ('activity', 'skill')

    def __str__(self):
        return f"{self.skill.name}: {self.points} pts"


class Project(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ProjectSubmission(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='project_submissions')
    image = models.ImageField(
        upload_to='project_submissions/images/', null=True, blank=True)
    document = models.FileField(
        upload_to='project_submissions/documents/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    evaluated = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'student')

    def __str__(self):
        return f"{self.student.username} - {self.project.title}"


class SkillAward(models.Model):
    submission = models.ForeignKey(
        ProjectSubmission, on_delete=models.CASCADE, related_name='skill_awards')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    points = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.skill.name}: {self.points} pts"


class PersonalTask(models.Model):
    DIFFICULTY_CHOICES = [(1, 'Easy'), (2, 'Medium'), (3, 'Hard')]
    IMPORTANCE_CHOICES = [(1, 'Low'), (2, 'Medium'), (3, 'High')]
    REPEAT_CHOICES = [
        ('none', 'Does not repeat'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]
    WEEKDAY_CHOICES = [
        ('mon', 'Mon'), ('tue', 'Tue'), ('wed', 'Wed'), ('thu', 'Thu'),
        ('fri', 'Fri'), ('sat', 'Sat'), ('sun', 'Sun'),
    ]

    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='personal_tasks')
    title = models.CharField(max_length=200)
    no_deadline = models.BooleanField(default=False)
    deadline = models.DateField(null=True, blank=True)
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES)
    importance = models.IntegerField(choices=IMPORTANCE_CHOICES)

    skill_main = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name='personal_tasks_main')
    skill_secondary = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='personal_tasks_secondary')
    skill_tertiary = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='personal_tasks_tertiary')

    repeat = models.CharField(
        max_length=10, choices=REPEAT_CHOICES, default='none')
    weekly_days = models.CharField(max_length=50, blank=True)
    notify = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)

    @property
    def due_soon(self):
        if self.no_deadline or not self.deadline:
            return False
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    @property
    def points_value(self):
        return self.difficulty * self.importance * 10

    @property
    def main_points(self):
        return self.points_value * 5 // 10

    @property
    def secondary_points(self):
        return self.points_value * 3 // 10

    @property
    def tertiary_points(self):
        return self.points_value * 2 // 10

    def get_weekly_days_display(self):
        if not self.weekly_days:
            return ''
        day_dict = dict(self.WEEKDAY_CHOICES)
        return ', '.join(day_dict.get(d, d) for d in self.weekly_days.split(','))

    def __str__(self):
        return self.title
