from tracker.models import Activity, Assignment, Quiz, Project


def profile_banner(request):
    if not request.user.is_authenticated or request.user.profile.role != 'student':
        return {}
    top_skill = request.user.skills.order_by('-points').first()

    enrolled_subjects = request.user.subjects_enrolled.all()

    activities_pending = Activity.objects.filter(
        topic__lesson_plan__subject__in=enrolled_subjects
    ).exclude(
        completions__student=request.user, completions__graded=True
    ).count()

    assignments_pending = Assignment.objects.filter(
        topic__lesson_plan__subject__in=enrolled_subjects
    ).exclude(
        completions__student=request.user, completions__graded=True
    ).count()

    quizzes_pending = Quiz.objects.filter(
        topic__lesson_plan__subject__in=enrolled_subjects
    ).exclude(
        completions__student=request.user, completions__graded=True
    ).count()

    projects_pending = Project.objects.filter(
        subject__in=enrolled_subjects
    ).exclude(
        submissions__student=request.user, submissions__evaluated=True
    ).count()

    profile_stats = {
        'personal_tasks': request.user.personal_tasks.count(),
        'activities': activities_pending,
        'assignments': assignments_pending,
        'quizzes': quizzes_pending,
        'projects': projects_pending,
    }
    return {'top_skill': top_skill, 'profile_stats': profile_stats}