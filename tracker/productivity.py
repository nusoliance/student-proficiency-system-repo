from django.utils import timezone
from datetime import datetime

from .models import (
    PersonalTask,
    Activity, ActivityCompletion,
    Assignment, AssignmentCompletion,
    Project, ProjectSubmission,
)


SCORE_POOL_RATIO = 0.2
EARLY_POOL_RATIO = 0.2
EARLY_CAP_DAYS = 5 
MISS_PENALTY_RATIO = 0.2 



def _adjust_productivity(profile, delta):
    """Apply delta to a profile's productivity points, never letting it drop below 0."""
    profile.productivity_points = max(0, profile.productivity_points + delta)
    profile.save(update_fields=['productivity_points'])


def _score_and_earliness_gain(max_score, score, deadline, completed_date):
    if not max_score:
        return 0
    score = score or 0
    score_factor = max(0.0, min(1.0, score / max_score))
    days_early = max(0, (deadline - completed_date).days)
    earliness_factor = min(days_early, EARLY_CAP_DAYS) / EARLY_CAP_DAYS
    gain = (max_score * SCORE_POOL_RATIO * score_factor) + \
        (max_score * EARLY_POOL_RATIO * earliness_factor)
    return round(gain)


def _process_missed_deadlines(profile, user, queryset, completion_related_name):
    """Generic pass for Activity/Assignment/Project: penalize items whose deadline
    has passed with no completion/submission at all from this student."""
    exclude_kwargs = {f'{completion_related_name}__student': user}
    overdue = queryset.exclude(
        productivity_penalized_students=user
    ).exclude(**exclude_kwargs)
    for item in overdue:
        penalty = round(item.max_score * MISS_PENALTY_RATIO)
        _adjust_productivity(profile, -penalty)
        item.productivity_penalized_students.add(user)


def sync_productivity(user):
    """Lazily reconciles a student's productivity points: applies missed-deadline
    penalties and awards points for anything graded/evaluated since the last check.
    Safe to call on every request - already-processed items are skipped."""
    if not user.is_authenticated or user.profile.role != 'student':
        return

    profile = user.profile
    now = timezone.now()
    today = now.date()

    # Personal tasks (with a time slot)
    if user.profile.mode == 'personal':
        pending_tasks = PersonalTask.objects.filter(
            student=user, productivity_processed=False,
            start_time__isnull=False, end_time__isnull=False,
            no_deadline=False, deadline__isnull=False,
        )
        for task in pending_tasks:
            task_end = datetime.combine(task.deadline, task.end_time)
            if timezone.is_naive(task_end):
                task_end = timezone.make_aware(task_end)
            if now > task_end:
                if task.completed:
                    _adjust_productivity(profile, task.points_value)
                else:
                    _adjust_productivity(profile, -task.points_value)
                task.productivity_processed = True
                task.save(update_fields=['productivity_processed'])

    enrolled_subjects = user.subjects_enrolled.all()

    # Activities
    _process_missed_deadlines(
        profile, user,
        Activity.objects.filter(
            topic__lesson_plan__subject__in=enrolled_subjects, deadline__lt=today),
        'completions')

    for completion in ActivityCompletion.objects.filter(
            student=user, graded=True, productivity_processed=False):
        gain = _score_and_earliness_gain(
            completion.activity.max_score, completion.score,
            completion.activity.deadline, completion.completed_at.date())
        _adjust_productivity(profile, gain)
        completion.productivity_processed = True
        completion.save(update_fields=['productivity_processed'])

    # Assignments
    _process_missed_deadlines(
        profile, user,
        Assignment.objects.filter(
            topic__lesson_plan__subject__in=enrolled_subjects, deadline__lt=today),
        'completions')

    for completion in AssignmentCompletion.objects.filter(
            student=user, graded=True, productivity_processed=False):
        gain = _score_and_earliness_gain(
            completion.assignment.max_score, completion.score,
            completion.assignment.deadline, completion.completed_at.date())
        _adjust_productivity(profile, gain)
        completion.productivity_processed = True
        completion.save(update_fields=['productivity_processed'])

    # Projects
    _process_missed_deadlines(
        profile, user,
        Project.objects.filter(
            subject__in=enrolled_subjects, deadline__isnull=False, deadline__lt=today),
        'submissions')

    for submission in ProjectSubmission.objects.filter(
            student=user, evaluated=True, productivity_processed=False):
        gain = _score_and_earliness_gain(
            submission.project.max_score, submission.score,
            submission.project.deadline, submission.submitted_at.date())
        _adjust_productivity(profile, gain)
        submission.productivity_processed = True
        submission.save(update_fields=['productivity_processed'])