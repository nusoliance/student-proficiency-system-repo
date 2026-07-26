from django.contrib import admin, messages
from django.core.mail import send_mail
from .models import Profile


@admin.action(description="Delete selected account(s) and notify by email (wrong school ID)")
def delete_and_notify_wrong_id(modeladmin, request, queryset):
    count = 0
    for profile in queryset:
        user = profile.user
        email = user.email
        username = user.username
        if email:
            send_mail(
                'Your Student Proficiency System account was removed',
                f"Hi {username},\n\nYour account was removed because it shared a School ID with another "
                f"student's account, and after review it was determined this ID does not belong to you. "
                f"If you believe this is a mistake, please contact your teacher.\n\n"
                f"- Student Proficiency System",
                None, [email],
            )
        user.delete()
        count += 1

    modeladmin.message_user(
        request, f"Deleted {count} account(s) and sent notification email(s).", messages.SUCCESS)


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'mode', 'school',
                    'school_id', 'under_evaluation')
    list_filter = ('role', 'mode', 'school', 'under_evaluation')
    actions = [delete_and_notify_wrong_id]


admin.site.register(Profile, ProfileAdmin)
