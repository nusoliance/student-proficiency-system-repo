from django.contrib import admin
from .models import ForumPost, Answer, Bookmark, Report

admin.site.register(ForumPost)
admin.site.register(Answer)
admin.site.register(Bookmark)
admin.site.register(Report)
