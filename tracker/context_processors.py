from django.utils import timezone
from .models import Subject, Activity, Project, ProjectSubmission, PersonalTask, ActivityCompletion


def reminders(request):
    if not request.user.is_authenticated or request.user.profile.role != 'student':
        return {}

    if request.user.profile.is_manager:
        owned = Subject.objects.filter(teacher=request.user)
    else:
        owned = Subject.objects.none()
    enrolled = request.user.subjects_enrolled.all()
    subjects = (owned | enrolled).distinct()

    items = []

    activities = Activity.objects.filter(
        topic__lesson_plan__subject__in=subjects)
    completed_ids = set(ActivityCompletion.objects.filter(
        student=request.user).values_list('activity_id', flat=True))
    for a in activities:
        if a.due_soon and a.id not in completed_ids:
            items.append({'title': a.title, 'deadline': a.deadline,
                         'type': 'Activity', 'url_name': 'activity_detail', 'obj_id': a.id})

    projects = Project.objects.filter(
        subject__in=subjects, deadline__isnull=False)
    for p in projects:
        submitted = ProjectSubmission.objects.filter(
            project=p, student=request.user).exists()
        if 0 <= (p.deadline - timezone.now().date()).days <= 3 and not submitted:
            items.append({'title': p.title, 'deadline': p.deadline,
                         'type': 'Project', 'url_name': 'project_detail', 'obj_id': p.id})

    if request.user.profile.mode == 'personal':
        personal_tasks = PersonalTask.objects.filter(
            student=request.user, completed=False, notify=True)
        for t in personal_tasks:
            if t.due_soon:
                items.append({'title': t.title, 'deadline': t.deadline, 'type': 'Task',
                             'url_name': 'personal_task_detail', 'obj_id': t.id})

    return {'reminder_items': items, 'reminder_count': len(items)}
