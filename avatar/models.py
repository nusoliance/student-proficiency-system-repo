from django.db import models
from django.contrib.auth.models import User


class Skill(models.Model):
    name = models.CharField(max_length=100)

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

    def __str__(self):
        return f"{self.student.username} - {self.skill.name} (Lv{self.level})"
