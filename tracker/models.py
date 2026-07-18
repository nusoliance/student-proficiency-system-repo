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
    skills = models.ManyToManyField(
        Skill, blank=True, related_name='activities')
    completed_by = models.ManyToManyField(
        User, blank=True, related_name='completed_activities')

    @property
    def due_soon(self):
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    def __str__(self):
        return self.title
