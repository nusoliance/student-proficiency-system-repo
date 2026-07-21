from django.db import models
from django.contrib.auth.models import User


class Course(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Skill(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General Education'),
        ('course', 'Course-Specific'),
        ('broad', 'Broad (Non-College)'),
    ]
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=10, choices=CATEGORY_CHOICES, default='course')
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, null=True, blank=True, related_name='skills')

    def __str__(self):
        return self.name


class StudentSkill(models.Model):
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('student', 'skill')

    @property
    def level(self):
        return self.points // 100

    @property
    def points_into_level(self):
        return self.points % 100

    @property
    def points_needed_for_level(self):
        return 100

    def __str__(self):
        return f"{self.student.username} - {self.skill.name} (Lv{self.level})"
