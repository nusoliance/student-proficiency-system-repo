from django.contrib import admin
from .models import Subject, LessonPlan, Topic, Activity, ActivitySkillPoints, Project, ProjectSubmission, SkillAward, ActivityCompletion, PersonalTask

admin.site.register(Subject)
admin.site.register(LessonPlan)
admin.site.register(Topic)
admin.site.register(Activity)
admin.site.register(ActivitySkillPoints)
admin.site.register(ActivityCompletion)
admin.site.register(PersonalTask)
