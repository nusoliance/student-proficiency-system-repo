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
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)

    def __str__(self):
        return f"Week {self.week_number}: {self.title}"


class Activity(models.Model):
    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name='activities')
    title = models.CharField(max_length=200)
    deadline = models.DateField()
    completed_by = models.ManyToManyField(
        User, blank=True, related_name='completed_activities')

    @property
    def due_soon(self):
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    def __str__(self):
        return self.title


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

    def __str__(self):
        return self.title


class ProjectSubmission(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='project_submissions')
    content = models.TextField()
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
