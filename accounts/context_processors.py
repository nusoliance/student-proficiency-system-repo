def profile_banner(request):
    if not request.user.is_authenticated or request.user.profile.role != 'student':
        return {}
    top_skill = request.user.skills.order_by('-points').first()
    profile_stats = {
        'personal_tasks': request.user.personal_tasks.filter(completed=True).count(),
        'activities': request.user.activity_completions.count(),
        'assignments': request.user.assignment_completions.count(),
        'quizzes': request.user.quiz_completions.count(),
        'projects': request.user.project_submissions.count(),
    }
    return {'top_skill': top_skill, 'profile_stats': profile_stats}