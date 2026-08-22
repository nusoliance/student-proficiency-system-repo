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
    teacher_school = request.user.profile.school

    if not teacher_school:
        return render(request, 'avatar/student_directory.html', {
            'students': User.objects.none(), 'query': query, 'no_school': True
        })

    students = User.objects.filter(
        profile__role='student', profile__mode='professional', profile__school=teacher_school)
    if query:
        students = students.filter(username__icontains=query)
    return render(request, 'avatar/student_directory.html', {
        'students': students, 'query': query, 'no_school': False
    })


@login_required
@user_passes_test(is_teacher)
def view_student_skills(request, student_id):
    student = get_object_or_404(
        User, id=student_id, profile__role='student',
        profile__school=request.user.profile.school)
    student_skills = student.skills.filter(
        skill__category__in=['course', 'general']).select_related('skill')
    course_skills = student_skills.filter(skill__category='course')
    general_skills = student_skills.filter(skill__category='general')
    return render(request, 'avatar/view_student_skills.html', {
        'student': student, 'course_skills': course_skills, 'general_skills': general_skills
    })


def _skill_entries(student_skills_qs):
    return [
        {
            'name': s.skill.name,
            'level': s.level,
            'into_level': s.points_into_level,
            'needed': s.points_needed_for_level,
        }
        for s in student_skills_qs
    ]


@login_required
def my_skills(request):
    student_skills = request.user.skills.select_related('skill').all()
    course_skills = student_skills.filter(skill__category='course')
    general_skills = student_skills.filter(skill__category='general')
    broad_skills = student_skills.filter(skill__category='broad')

    pages = []
    if course_skills:
        pages.append({'label': 'Course Skills', 'entries': _skill_entries(course_skills)})
    if general_skills:
        pages.append({'label': 'General Education Skills', 'entries': _skill_entries(general_skills)})
    if broad_skills:
        pages.append({'label': 'Skills', 'entries': _skill_entries(broad_skills)})

    profile = request.user.profile
    pages.append({
        'label': 'Personal Skills',
        'entries': [
            {
                'name': 'Productivity',
                'level': profile.productivity_level,
                'into_level': profile.productivity_into_level,
                'needed': 100,
            },
        ],
    })

    return render(request, 'avatar/my_skills.html', {'pages': pages})
