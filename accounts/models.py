from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
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
    SCHOOL_CHOICES = [
        ('citu', 'Cebu Institute of Technology-University'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    mode = models.CharField(
        max_length=15, choices=MODE_CHOICES, blank=True, null=True)
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True)
    school = models.CharField(
        max_length=10, choices=SCHOOL_CHOICES, blank=True)
    school_id = models.CharField(max_length=12, blank=True)
    under_evaluation = models.BooleanField(default=False)
    middle_initial = models.CharField(max_length=4, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_manager(self):
        return self.role == 'teacher' or self.mode == 'personal'

    @property
    def full_display_name(self):
        """'Last Name, First Name M.' — falls back to the username if the
        student hasn't filled in their name yet."""
        if self.user.last_name and self.user.first_name:
            name = f"{self.user.last_name}, {self.user.first_name}"
            if self.middle_initial:
                name += f" {self.middle_initial}"
            return name
        return self.user.username


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, role='student')


@receiver(post_delete, sender=Profile)
def clear_stale_evaluation_flag(sender, instance, **kwargs):
    """
    When a profile is deleted (e.g. a duplicate/fake school-ID account is
    removed), re-check whether any remaining account sharing that school ID
    is still ambiguous. If only one account is left holding the ID, it's no
    longer a conflict, so clear its 'under_evaluation' flag.

    This runs on ANY Profile deletion path - admin panel default delete,
    the custom delete-and-notify action, cascading deletes from removing a
    User, or manage.py shell - so the warning never gets left stale again.
    """
    school_id = instance.school_id
    if instance.school != 'citu' or not school_id:
        return
    remaining = Profile.objects.filter(school='citu', school_id=school_id)
    if remaining.count() <= 1:
        remaining.update(under_evaluation=False)
