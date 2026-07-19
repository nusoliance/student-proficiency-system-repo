from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404


def is_teacher(user):
    return user.is_authenticated and user.profile.role == 'teacher'


@login_required
@user_passes_test(is_teacher)
def student_directory(request):
    query = request.GET.get('q', '')
    students = User.objects.filter(
        profile__role='student', profile__mode='professional')
    if query:
        students = students.filter(username__icontains=query)
    return render(request, 'avatar/student_directory.html', {'students': students, 'query': query})


@login_required
@user_passes_test(is_teacher)
def view_student_skills(request, student_id):
    student = get_object_or_404(User, id=student_id, profile__role='student')
    student_skills = student.skills.all()
    return render(request, 'avatar/view_student_skills.html', {'student': student, 'student_skills': student_skills})


@login_required
def my_skills(request):
    student_skills = request.user.skills.all()
    return render(request, 'avatar/my_skills.html', {'student_skills': student_skills})
