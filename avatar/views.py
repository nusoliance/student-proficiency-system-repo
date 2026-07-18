from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def my_skills(request):
    student_skills = request.user.skills.all()
    return render(request, 'avatar/my_skills.html', {'student_skills': student_skills})
