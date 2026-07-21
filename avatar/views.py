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
    student_skills = student.skills.filter(
        skill__category__in=['course', 'general']).select_related('skill')
    course_skills = student_skills.filter(skill__category='course')
    general_skills = student_skills.filter(skill__category='general')
    return render(request, 'avatar/view_student_skills.html', {
        'student': student, 'course_skills': course_skills, 'general_skills': general_skills
    })


@login_required
def my_skills(request):
    student_skills = request.user.skills.select_related('skill').all()
    course_skills = student_skills.filter(skill__category='course')
    general_skills = student_skills.filter(skill__category='general')
    broad_skills = student_skills.filter(skill__category='broad')
    return render(request, 'avatar/my_skills.html', {
        'course_skills': course_skills, 'general_skills': general_skills, 'broad_skills': broad_skills
    })
