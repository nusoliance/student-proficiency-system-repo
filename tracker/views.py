from django.shortcuts import get_object_or_404
from .models import Subject, LessonPlan, Topic, Activity, ActivityCompletion, ActivitySkillPoints, Project, ProjectSubmission, SkillAward, PersonalTask
from .forms import SubjectForm, TopicForm, ActivityForm, ActivitySkillPointsForm, ProjectForm, SubmissionForm, SkillAwardForm, ManageStudentsForm, ActivityCompletionForm, TaskActivityForm, TaskProjectForm, PersonalTaskForm
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import calendar as cal_module
from django.db.models import Q, Case, When, Value, IntegerField
from avatar.models import Skill


def get_relevant_skills():
    return Skill.objects.exclude(category='broad').annotate(
        category_order=Case(
            When(category='general', then=Value(0)),
            When(category='course', then=Value(1)),
            output_field=IntegerField(),
        )
    ).order_by('category_order', 'course__name', 'name')


@login_required
def subject_list(request):
    if request.user.profile.is_manager:
        owned = Subject.objects.filter(teacher=request.user)
    else:
        owned = Subject.objects.none()
    enrolled = request.user.subjects_enrolled.all()
    subjects = (owned | enrolled).distinct()

    subject_data = []
    for subject in subjects:
        due_count = 0
        for topic in subject.lesson_plan.topics.all():
            for activity in topic.activities.all():
                completed = ActivityCompletion.objects.filter(
                    activity=activity, student=request.user).exists()
                if activity.due_soon and not completed:
                    due_count += 1
        for project in subject.projects.filter(deadline__isnull=False):
            submitted = ProjectSubmission.objects.filter(
                project=project, student=request.user).exists()
            if 0 <= (project.deadline - timezone.now().date()).days <= 3 and not submitted:
                due_count += 1
        subject_data.append({'subject': subject, 'due_count': due_count})

    return render(request, 'tracker/subject_list.html', {'subject_data': subject_data})


@login_required
def add_subject(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST, user=request.user)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.teacher = request.user
            subject.save()
            form.save_m2m()
            if request.user.profile.mode == 'personal':
                subject.students.add(request.user)
            LessonPlan.objects.create(subject=subject)
            return redirect('subject_list')
    else:
        form = SubjectForm(user=request.user)
    return render(request, 'tracker/add_subject.html', {'form': form})


@login_required
def lesson_plan_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    topics = subject.lesson_plan.topics.all().order_by('start_date')
    activity_ids = Activity.objects.filter(
        topic__lesson_plan__subject=subject).values_list('id', flat=True)
    completed_activity_ids = set(
        ActivityCompletion.objects.filter(
            student=request.user, activity_id__in=activity_ids).values_list('activity_id', flat=True)
    )
    return render(request, 'tracker/lesson_plan.html', {
        'subject': subject, 'topics': topics, 'completed_activity_ids': completed_activity_ids
    })


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
            return redirect('add_activity_skill', activity_id=activity.id)
    else:
        form = ActivityForm()
    return render(request, 'tracker/add_activity.html', {'form': form, 'topic': topic})


@login_required
def add_activity_skill(request, activity_id):
    activity = get_object_or_404(Activity, id=activity_id)
    subject = activity.topic.lesson_plan.subject
    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = ActivitySkillPointsForm(
            request.POST, skill_queryset=relevant_skills)
        if form.is_valid():
            skill_points = form.save(commit=False)
            skill_points.activity = activity
            skill_points.save()
            return redirect('add_activity_skill', activity_id=activity.id)
    else:
        form = ActivitySkillPointsForm(skill_queryset=relevant_skills)
    return render(request, 'tracker/add_activity_skill.html', {
        'activity': activity, 'form': form, 'skills': relevant_skills
    })


@login_required
def activity_detail(request, activity_id):
    activity = get_object_or_404(Activity, id=activity_id)
    subject = activity.topic.lesson_plan.subject
    is_owner = subject.teacher == request.user
    is_personal = request.user.profile.mode == 'personal'

    if is_owner and is_personal:
        completion = ActivityCompletion.objects.filter(
            activity=activity, student=request.user).first()
        if request.method == 'POST' and not completion:
            form = ActivityCompletionForm(request.POST, request.FILES)
            if form.is_valid():
                completion = form.save(commit=False)
                completion.activity = activity
                completion.student = request.user
                completion.save()
                for sp in activity.skill_points.all():
                    student_skill, created = request.user.skills.get_or_create(
                        skill=sp.skill)
                    student_skill.points += sp.points
                    student_skill.save()
                return redirect('activity_detail', activity_id=activity.id)
        else:
            form = ActivityCompletionForm()
        return render(request, 'tracker/activity_detail_personal.html', {'activity': activity, 'completion': completion, 'form': form})

    if is_owner:
        completions = activity.completions.select_related('student').all()
        return render(request, 'tracker/activity_detail_teacher.html', {'activity': activity, 'completions': completions})

    completion = ActivityCompletion.objects.filter(
        activity=activity, student=request.user).first()
    if request.method == 'POST' and not completion:
        form = ActivityCompletionForm(request.POST, request.FILES)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.activity = activity
            completion.student = request.user
            completion.save()
            for sp in activity.skill_points.all():
                student_skill, created = request.user.skills.get_or_create(
                    skill=sp.skill)
                student_skill.points += sp.points
                student_skill.save()
            return redirect('activity_detail', activity_id=activity.id)
    else:
        form = ActivityCompletionForm()
    return render(request, 'tracker/activity_detail.html', {'activity': activity, 'completion': completion, 'form': form})


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
    is_owner = project.subject.teacher == request.user
    is_personal = request.user.profile.mode == 'personal'

    if is_owner and is_personal:
        submission = ProjectSubmission.objects.filter(
            project=project, student=request.user).first()
        if request.method == 'POST' and not submission:
            form = SubmissionForm(request.POST, request.FILES)
            if form.is_valid():
                submission = form.save(commit=False)
                submission.project = project
                submission.student = request.user
                submission.save()
                return redirect('project_detail', project_id=project.id)
        else:
            form = SubmissionForm()
        return render(request, 'tracker/project_detail_personal.html', {'project': project, 'submission': submission, 'form': form})

    if is_owner:
        submissions = project.submissions.all()
        return render(request, 'tracker/project_detail_teacher.html', {'project': project, 'submissions': submissions})

    submission = ProjectSubmission.objects.filter(
        project=project, student=request.user).first()
    if request.method == 'POST' and not submission:
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.project = project
            sub.student = request.user
            sub.save()
            return redirect('project_detail', project_id=project.id)
    else:
        form = SubmissionForm()
    return render(request, 'tracker/project_detail_student.html', {'project': project, 'submission': submission, 'form': form})


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
    if subject.teacher.profile.mode == 'personal':
        return redirect('lesson_plan_view', subject_id=subject.id)

    query = request.GET.get('q', '')
    results = []
    if query:
        results = User.objects.filter(
            profile__role='student', profile__mode='professional', username__icontains=query
        ).exclude(id__in=subject.students.values_list('id', flat=True))
    return render(request, 'tracker/manage_students.html', {
        'subject': subject, 'query': query, 'results': results
    })


@login_required
def add_student_to_subject(request, subject_id, student_id):
    subject = get_object_or_404(Subject, id=subject_id)
    student = get_object_or_404(User, id=student_id)
    subject.students.add(student)
    return redirect('manage_students', subject_id=subject.id)


@login_required
def remove_student_from_subject(request, subject_id, student_id):
    subject = get_object_or_404(Subject, id=subject_id)
    student = get_object_or_404(User, id=student_id)
    subject.students.remove(student)
    return redirect('manage_students', subject_id=subject.id)


@login_required
def task_list(request):
    if request.user.profile.is_manager:
        owned = Subject.objects.filter(teacher=request.user)
    else:
        owned = Subject.objects.none()
    enrolled = request.user.subjects_enrolled.all()
    subjects = (owned | enrolled).distinct()

    activities = Activity.objects.filter(
        topic__lesson_plan__subject__in=subjects).order_by('deadline')
    completed_activity_ids = set(
        ActivityCompletion.objects.filter(
            student=request.user, activity__in=activities).values_list('activity_id', flat=True)
    )

    projects = Project.objects.filter(
        subject__in=subjects).order_by('deadline')
    project_data = []
    for project in projects:
        submission = ProjectSubmission.objects.filter(
            project=project, student=request.user).first()
        project_data.append({'project': project, 'submission': submission})

    return render(request, 'tracker/task_list.html', {
        'activities': activities, 'completed_activity_ids': completed_activity_ids, 'project_data': project_data
    })


@login_required
def add_task_activity(request):
    if not (request.user.profile.role == 'student' and request.user.profile.mode == 'personal'):
        return redirect('task_list')
    if request.method == 'POST':
        form = TaskActivityForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('task_list')
    else:
        form = TaskActivityForm(user=request.user)
    return render(request, 'tracker/add_task_activity.html', {'form': form})


@login_required
def add_task_project(request):
    if not (request.user.profile.role == 'student' and request.user.profile.mode == 'personal'):
        return redirect('task_list')
    if request.method == 'POST':
        form = TaskProjectForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('task_list')
    else:
        form = TaskProjectForm(user=request.user)
    return render(request, 'tracker/add_task_project.html', {'form': form})


@login_required
def personal_task_list(request):
    if request.user.profile.mode != 'personal':
        return redirect('task_list')
    tasks = PersonalTask.objects.filter(
        student=request.user).order_by('deadline')
    return render(request, 'tracker/personal_task_list.html', {'tasks': tasks})


@login_required
def add_personal_task(request):
    if request.user.profile.mode != 'personal':
        return redirect('task_list')
    if request.method == 'POST':
        form = PersonalTaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.student = request.user
            task.save()
            form.save_m2m()
            return redirect('personal_task_list')
    else:
        form = PersonalTaskForm(user=request.user)
    return render(request, 'tracker/add_personal_task.html', {'form': form})


@login_required
def complete_personal_task(request, task_id):
    task = get_object_or_404(PersonalTask, id=task_id, student=request.user)
    if not task.completed:
        task.completed = True
        task.save()
        awards = [(task.skill_main, task.main_points)]
        if task.skill_secondary:
            awards.append((task.skill_secondary, task.secondary_points))
        if task.skill_tertiary:
            awards.append((task.skill_tertiary, task.tertiary_points))
        for skill, points in awards:
            student_skill, created = request.user.skills.get_or_create(
                skill=skill)
            student_skill.points += points
            student_skill.save()
    return redirect('personal_task_detail', task_id=task.id)


@login_required
def personal_task_detail(request, task_id):
    task = get_object_or_404(PersonalTask, id=task_id, student=request.user)
    return render(request, 'tracker/personal_task_detail.html', {'task': task})


@login_required
def calendar_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    today = timezone.now().date()
    c = cal_module.Calendar(firstweekday=0)
    month_weeks = c.monthdatescalendar(today.year, today.month)

    topics = subject.lesson_plan.topics.all()
    projects = subject.projects.filter(deadline__isnull=False)

    weeks_data = []
    for week in month_weeks:
        week_start, week_end = week[0], week[-1]
        bars = []
        row = 1

        for topic in topics:
            if topic.end_date < week_start or topic.start_date > week_end:
                continue
            bar_start = max(topic.start_date, week_start)
            bar_end = min(topic.end_date, week_end)
            bars.append({
                'label': topic.title,
                'css_class': 'cal-topic-bar',
                'col_start': (bar_start - week_start).days + 1,
                'col_span': (bar_end - bar_start).days + 1,
                'row': row,
                'url_name': 'lesson_plan_view', 'obj_id': subject.id,
            })
            row += 1

            for activity in topic.activities.all():
                a_start, a_end = activity.created_at.date(), activity.deadline
                if a_end < week_start or a_start > week_end:
                    continue
                ib_start = max(a_start, week_start)
                ib_end = min(a_end, week_end)
                bars.append({
                    'label': activity.title,
                    'css_class': 'cal-item-bar cal-activity-bar',
                    'col_start': (ib_start - week_start).days + 1,
                    'col_span': (ib_end - ib_start).days + 1,
                    'row': row,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                })
                row += 1

        for project in projects:
            p_start, p_end = project.created_at.date(), project.deadline
            if p_end < week_start or p_start > week_end:
                continue
            ib_start = max(p_start, week_start)
            ib_end = min(p_end, week_end)
            bars.append({
                'label': f"Project: {project.title}",
                'css_class': 'cal-item-bar cal-project-bar',
                'col_start': (ib_start - week_start).days + 1,
                'col_span': (ib_end - ib_start).days + 1,
                'row': row,
                'url_name': 'project_detail', 'obj_id': project.id,
            })
            row += 1

        weeks_data.append({'days': week, 'bars': bars, 'row_count': row})

    return render(request, 'tracker/calendar_view.html', {
        'subject': subject, 'weeks_data': weeks_data, 'month_name': today.strftime('%B %Y'), 'today': today
    })


@login_required
def delete_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    if request.method == 'POST':
        subject.delete()
        return redirect('subject_list')
    return render(request, 'tracker/confirm_delete.html', {'object_name': subject.name, 'cancel_url': 'subject_list'})


@login_required
def delete_topic(request, topic_id):
    topic = get_object_or_404(
        Topic, id=topic_id, lesson_plan__subject__teacher=request.user)
    subject_id = topic.lesson_plan.subject.id
    if request.method == 'POST':
        topic.delete()
        return redirect('lesson_plan_view', subject_id=subject_id)
    return render(request, 'tracker/confirm_delete.html', {'object_name': topic.title, 'cancel_url': 'lesson_plan_view', 'cancel_arg': subject_id})


@login_required
def delete_activity(request, activity_id):
    activity = get_object_or_404(
        Activity, id=activity_id, topic__lesson_plan__subject__teacher=request.user)
    subject_id = activity.topic.lesson_plan.subject.id
    if request.method == 'POST':
        activity.delete()
        return redirect('lesson_plan_view', subject_id=subject_id)
    return render(request, 'tracker/confirm_delete.html', {'object_name': activity.title, 'cancel_url': 'lesson_plan_view', 'cancel_arg': subject_id})


@login_required
def delete_project(request, project_id):
    project = get_object_or_404(
        Project, id=project_id, subject__teacher=request.user)
    subject_id = project.subject.id
    if request.method == 'POST':
        project.delete()
        return redirect('lesson_plan_view', subject_id=subject_id)
    return render(request, 'tracker/confirm_delete.html', {'object_name': project.title, 'cancel_url': 'lesson_plan_view', 'cancel_arg': subject_id})


@login_required
def delete_personal_task(request, task_id):
    task = get_object_or_404(PersonalTask, id=task_id, student=request.user)
    if request.method == 'POST':
        task.delete()
        return redirect('personal_task_list')
    return render(request, 'tracker/confirm_delete.html', {'object_name': task.title, 'cancel_url': 'personal_task_list'})
