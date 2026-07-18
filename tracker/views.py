from django.shortcuts import get_object_or_404
from .forms import SubjectForm, TopicForm, ActivityForm, ProjectForm, SubmissionForm, SkillAwardForm, ManageStudentsForm
from .models import Subject, LessonPlan, Topic, Activity, Project, ProjectSubmission, SkillAward
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta


@login_required
def subject_list(request):
    if request.user.profile.role == 'teacher':
        subjects = Subject.objects.filter(teacher=request.user)
    else:
        subjects = request.user.subjects_enrolled.all()
    return render(request, 'tracker/subject_list.html', {'subjects': subjects})


@login_required
def add_subject(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.teacher = request.user
            subject.save()
            form.save_m2m()
            LessonPlan.objects.create(subject=subject)
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'tracker/add_subject.html', {'form': form})


@login_required
def lesson_plan_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    topics = subject.lesson_plan.topics.all().order_by('week_number')
    return render(request, 'tracker/lesson_plan.html', {'subject': subject, 'topics': topics})


@login_required
def add_topic(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        form = TopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.lesson_plan = subject.lesson_plan
            topic.save()
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        form = TopicForm()
    return render(request, 'tracker/add_topic.html', {'form': form, 'subject': subject})


@login_required
def add_activity(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    if request.method == 'POST':
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.topic = topic
            activity.save()
            form.save_m2m()
            return redirect('lesson_plan_view', subject_id=topic.lesson_plan.subject.id)
    else:
        form = ActivityForm()
    return render(request, 'tracker/add_activity.html', {'form': form, 'topic': topic})


@login_required
def mark_complete(request, activity_id):
    activity = get_object_or_404(Activity, id=activity_id)
    activity.completed_by.add(request.user)
    for skill in activity.skills.all():
        student_skill, created = request.user.skills.get_or_create(skill=skill)
        student_skill.points += 10
        student_skill.save()
    return redirect('lesson_plan_view', subject_id=activity.topic.lesson_plan.subject.id)


@login_required
def add_project(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.subject = subject
            project.save()
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        form = ProjectForm()
    return render(request, 'tracker/add_project.html', {'form': form, 'subject': subject})


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.user.profile.role == 'student':
        submission = ProjectSubmission.objects.filter(
            project=project, student=request.user).first()
        if request.method == 'POST' and not submission:
            form = SubmissionForm(request.POST)
            if form.is_valid():
                sub = form.save(commit=False)
                sub.project = project
                sub.student = request.user
                sub.save()
                return redirect('project_detail', project_id=project.id)
        else:
            form = SubmissionForm()
        return render(request, 'tracker/project_detail_student.html', {'project': project, 'submission': submission, 'form': form})
    else:
        submissions = project.submissions.all()
        return render(request, 'tracker/project_detail_teacher.html', {'project': project, 'submissions': submissions})


@login_required
def evaluate_submission(request, submission_id):
    submission = get_object_or_404(ProjectSubmission, id=submission_id)
    if request.method == 'POST':
        form = SkillAwardForm(request.POST, student=submission.student)
        if form.is_valid():
            award = form.save(commit=False)
            award.submission = submission
            award.save()
            student_skill, created = submission.student.skills.get_or_create(
                skill=award.skill)
            student_skill.points += award.points
            student_skill.save()
            return redirect('evaluate_submission', submission_id=submission.id)
    else:
        form = SkillAwardForm(student=submission.student)
    return render(request, 'tracker/evaluate_submission.html', {'submission': submission, 'form': form})


@login_required
def finish_evaluation(request, submission_id):
    submission = get_object_or_404(ProjectSubmission, id=submission_id)
    submission.evaluated = True
    submission.save()
    return redirect('project_detail', project_id=submission.project.id)


@login_required
def manage_students(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        form = ManageStudentsForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        form = ManageStudentsForm(instance=subject)
    return render(request, 'tracker/manage_students.html', {'form': form, 'subject': subject})
