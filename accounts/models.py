from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from avatar.models import Course


class Profile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]
    MODE_CHOICES = [
        ('personal', 'Personal'),
        ('professional', 'Professional'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    mode = models.CharField(
        max_length=15, choices=MODE_CHOICES, blank=True, null=True)
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_manager(self):
        return self.role == 'teacher' or self.mode == 'personal'


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, role='student')
