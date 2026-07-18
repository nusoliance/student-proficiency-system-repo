from django.db import models
from django.contrib.auth.models import User
from tracker.models import Subject
from avatar.models import Course


class ForumPost(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='posts', null=True, blank=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='posts', null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.username}: {self.text[:30]}"


class Answer(models.Model):
    post = models.ForeignKey(
        ForumPost, on_delete=models.CASCADE, related_name='answers')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'post')


class Report(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE)
    reason = models.CharField(max_length=200, blank=True)
