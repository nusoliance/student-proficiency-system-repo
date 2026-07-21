def profile_banner(request):
    if not request.user.is_authenticated or request.user.profile.role != 'student':
        return {}
    top_skill = request.user.skills.order_by('-points').first()
    return {'top_skill': top_skill}
