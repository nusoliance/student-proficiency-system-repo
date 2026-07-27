from django.shortcuts import get_object_or_404
from .models import Subject, LessonPlan, Topic, Activity, ActivityCompletion, Project, ProjectSubmission, SkillAward, PersonalTask, Skill
from .forms import SubjectForm, TopicForm, ActivityForm, ProjectForm, SubmissionForm, SkillAwardForm, ManageStudentsForm, ActivityCompletionForm, TaskActivityForm, TaskProjectForm, PersonalTaskForm, GradeActivityForm, GradeProjectForm, SubjectWeightsForm
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import calendar as cal_module
from django.db.models import Q, Case, When, Value, IntegerField
from avatar.models import Skill, StudentSkill
from django.contrib import messages
from datetime import date

def _points_for_score(activity, score):
    """Compute the (main, secondary, tertiary) skill points an activity
    would award for a given score, by reusing ActivityCompletion's own
    point-calculation properties on a throwaway (unsaved) instance so the
    math can never drift out of sync with the model."""
    if score is None:
        return 0, 0, 0
    temp = ActivityCompletion(activity=activity, score=score)
    return temp.main_points, temp.secondary_points, temp.tertiary_points


def _adjust_activity_skill_points(completion, activity, score, sign):
    """Add (sign=1) or remove (sign=-1) the skill points an activity
    awards for a given score, for the completion's student."""
    main, secondary, tertiary = _points_for_score(activity, score)
    awards = [(activity.skill_main, main)]
    if activity.skill_secondary:
        awards.append((activity.skill_secondary, secondary))
    if activity.skill_tertiary:
        awards.append((activity.skill_tertiary, tertiary))
    for skill, points in awards:
        if not skill_applies_to_student(skill, completion.student):
            continue
        student_skill, created = completion.student.skills.get_or_create(skill=skill)
        student_skill.points = max(0, student_skill.points + sign * points)
        student_skill.save()


def _award_activity_skill_points(completion, activity):
    _adjust_activity_skill_points(completion, activity, completion.score, sign=1)

def get_relevant_skills():
    return Skill.objects.exclude(category='broad').annotate(
        category_order=Case(
            When(category='general', then=Value(0)),
            When(category='course', then=Value(1)),
            output_field=IntegerField(),
        )
    ).order_by('category_order', 'course__name', 'name')


def skill_groups_for_picker(skills):
    groups = []
    group_by_name = {}
    for skill in skills.select_related('course'):
        group_name = 'General Education' if skill.category == 'general' else (
            skill.course.name if skill.course else 'Other')
        if group_name not in group_by_name:
            group_by_name[group_name] = {'course': group_name, 'skills': []}
            groups.append(group_by_name[group_name])
        group_by_name[group_name]['skills'].append(
            {'id': skill.id, 'name': skill.name})
    return groups


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
    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = ActivityForm(request.POST, relevant_skills=relevant_skills)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.topic = topic
            activity.save()
            return redirect('lesson_plan_view', subject_id=topic.lesson_plan.subject.id)
    else:
        form = ActivityForm(relevant_skills=relevant_skills)
    return render(request, 'tracker/add_activity.html', {
        'form': form, 'topic': topic,
        'skill_groups': skill_groups_for_picker(relevant_skills),
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
            return redirect('activity_detail', activity_id=activity.id)
    else:
        form = ActivityCompletionForm()
    return render(request, 'tracker/activity_detail.html', {'activity': activity, 'completion': completion, 'form': form})


@login_required
def grade_activity_completion(request, completion_id):
    completion = get_object_or_404(ActivityCompletion, id=completion_id)
    activity = completion.activity
    if activity.topic.lesson_plan.subject.teacher != request.user:
        return redirect('home')

    if request.method == 'POST':
        was_graded = completion.graded
        old_score = completion.score

        form = GradeActivityForm(
            request.POST, instance=completion, max_score=activity.max_score)
        if form.is_valid():
            if was_graded:
                _adjust_activity_skill_points(completion, activity, old_score, sign=-1)
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()

            _award_activity_skill_points(completion, activity)
            messages.success(request, 'Grade saved.')
            return redirect('grade_activity_completion', completion_id=completion.id)
    else:
        form = GradeActivityForm(
            instance=completion, max_score=activity.max_score)

    show_form = not completion.graded or request.GET.get('edit') == '1'
    return render(request, 'tracker/grade_activity_completion.html', {
        'completion': completion, 'activity': activity, 'form': form,
        'show_form': show_form,
    })

@login_required
def grade_activity_queue(request, activity_id):
    activity = get_object_or_404(Activity, id=activity_id)
    if activity.topic.lesson_plan.subject.teacher != request.user:
        return redirect('home')

    pending = activity.completions.filter(graded=False).select_related('student').order_by('completed_at')
    completion = pending.first()

    if not completion:
        return render(request, 'tracker/grade_queue_done.html', {
            'activity': activity, 'total_graded': activity.completions.filter(graded=True).count(),
        })

    remaining_count = pending.count()

    if request.method == 'POST':
        form = GradeActivityForm(request.POST, instance=completion, max_score=activity.max_score)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()
            _award_activity_skill_points(completion, activity)
            return redirect('grade_activity_queue', activity_id=activity.id)
    else:
        form = GradeActivityForm(instance=completion, max_score=activity.max_score)

    return render(request, 'tracker/grade_activity_queue.html', {
        'activity': activity, 'completion': completion, 'form': form, 'remaining_count': remaining_count,
    })

@login_required
def grade_subject_queue(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)

    pending = ActivityCompletion.objects.filter(
        activity__topic__lesson_plan__subject=subject, graded=False
    ).select_related('student', 'activity').order_by('completed_at')
    completion = pending.first()

    if not completion:
        return render(request, 'tracker/grade_subject_queue_done.html', {
            'subject': subject,
            'total_graded': ActivityCompletion.objects.filter(
                activity__topic__lesson_plan__subject=subject, graded=True).count(),
        })

    activity = completion.activity
    remaining_count = pending.count()

    if request.method == 'POST':
        form = GradeActivityForm(request.POST, instance=completion, max_score=activity.max_score)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()
            _award_activity_skill_points(completion, activity)
            return redirect('grade_subject_queue', subject_id=subject.id)
    else:
        form = GradeActivityForm(instance=completion, max_score=activity.max_score)

    return render(request, 'tracker/grade_subject_queue.html', {
        'subject': subject, 'activity': activity, 'completion': completion,
        'form': form, 'remaining_count': remaining_count,
    })

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
    project = submission.project
    if request.method == 'POST':
        if 'submit_score' in request.POST:
            score_form = GradeProjectForm(
                request.POST, instance=submission, max_score=project.max_score)
            if score_form.is_valid():
                score_form.save()
                return redirect('evaluate_submission', submission_id=submission.id)
            form = SkillAwardForm(student=submission.student)
        else:
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
            score_form = GradeProjectForm(
                instance=submission, max_score=project.max_score)
    else:
        form = SkillAwardForm(student=submission.student)
        score_form = GradeProjectForm(
            instance=submission, max_score=project.max_score)
    return render(request, 'tracker/evaluate_submission.html', {
        'submission': submission, 'form': form, 'score_form': score_form,
    })


@login_required
def finish_evaluation(request, submission_id):
    submission = get_object_or_404(ProjectSubmission, id=submission_id)
    submission.evaluated = True
    submission.save()
    return redirect('project_detail', project_id=submission.project.id)


def _build_gradesheet_row(subject, student, activities, projects, completion_map, submission_map, is_teacher=True):
    activity_cells = []
    project_cells = []
    activity_percentages = []
    project_percentages = []

    for activity in activities:
        completion = completion_map.get((student.id, activity.id))
        if completion is None:
            activity_cells.append({
                'status': 'not_submitted', 'score': None, 'max_score': activity.max_score,
                'url_name': 'activity_detail', 'obj_id': activity.id,
            })
        elif not completion.graded:
            activity_cells.append({
                'status': 'pending', 'score': None, 'max_score': activity.max_score,
                'url_name': 'activity_detail', 'obj_id': activity.id,
            })
        else:
            if activity.max_score:
                activity_percentages.append(
                    completion.score / activity.max_score * 100)
            activity_cells.append({
                'status': 'evaluated', 'score': completion.score, 'max_score': activity.max_score,
                'url_name': 'activity_detail', 'obj_id': activity.id,
            })

    for project in projects:
        submission = submission_map.get((student.id, project.id))
        if submission is None:
            project_cells.append({
                'status': 'not_submitted', 'score': None, 'max_score': project.max_score,
                'url_name': 'project_detail', 'obj_id': project.id,
            })
        elif not submission.evaluated:
            project_cells.append({
                'status': 'pending', 'score': None, 'max_score': project.max_score,
                'url_name': 'evaluate_submission' if is_teacher else 'project_detail',
                'obj_id': submission.id if is_teacher else project.id,
            })
        else:
            if project.max_score and submission.score is not None:
                project_percentages.append(
                    submission.score / project.max_score * 100)
            project_cells.append({
                'status': 'evaluated', 'score': submission.score, 'max_score': project.max_score,
                'url_name': 'evaluate_submission' if is_teacher else 'project_detail',
                'obj_id': submission.id if is_teacher else project.id,
            })

    activity_average = (
        sum(activity_percentages) / len(activity_percentages)
        if activity_percentages else None)
    project_average = (
        sum(project_percentages) / len(project_percentages)
        if project_percentages else None)

    if activity_average is not None and project_average is not None:
        average = (
            activity_average * subject.activity_weight
            + project_average * subject.project_weight) / 100
    elif activity_average is not None:
        average = activity_average
    elif project_average is not None:
        average = project_average
    else:
        average = None

    return {
        'student': student, 'activity_cells': activity_cells,
        'project_cells': project_cells, 'average': average,
        'activity_average': activity_average,
    }


def _rank_gradesheet_rows(rows):
    ranked = sorted(
        (r for r in rows if r['average'] is not None),
        key=lambda r: r['average'], reverse=True)
    rank = 0
    previous_average = None
    for i, row in enumerate(ranked, start=1):
        if row['average'] != previous_average:
            rank = i
            previous_average = row['average']
        row['rank'] = rank
    for row in rows:
        row.setdefault('rank', None)


def build_gradesheet_data(subject):
    students = subject.students.all().order_by(
    'last_name', 'first_name', 'username')
    activities = Activity.objects.filter(
        topic__lesson_plan__subject=subject).select_related('topic').order_by('deadline')
    projects = subject.projects.all().order_by('deadline')

    activity_completions = ActivityCompletion.objects.filter(
        activity__in=activities)
    completion_map = {
        (c.student_id, c.activity_id): c for c in activity_completions}

    submissions = ProjectSubmission.objects.filter(project__in=projects)
    submission_map = {
        (sub.student_id, sub.project_id): sub for sub in submissions}

    rows = []
    for student in students:
        activity_cells = []
        project_cells = []
        activity_percentages = []
        project_percentages = []

        for activity in activities:
            completion = completion_map.get((student.id, activity.id))
            if completion is None:
                activity_cells.append({
                    'status': 'not_submitted', 'score': None, 'max_score': activity.max_score,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                })
            elif not completion.graded:
                activity_cells.append({
                    'status': 'pending', 'score': None, 'max_score': activity.max_score,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                })
            else:
                if activity.max_score:
                    activity_percentages.append(
                        completion.score / activity.max_score * 100)
                activity_cells.append({
                    'status': 'evaluated', 'score': completion.score, 'max_score': activity.max_score,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                })

        for project in projects:
            submission = submission_map.get((student.id, project.id))
            if submission is None:
                project_cells.append({
                    'status': 'not_submitted', 'score': None, 'max_score': project.max_score,
                    'url_name': 'project_detail', 'obj_id': project.id,
                })
            elif not submission.evaluated:
                project_cells.append({
                    'status': 'pending', 'score': None, 'max_score': project.max_score,
                    'url_name': 'evaluate_submission', 'obj_id': submission.id,
                })
            else:
                if project.max_score and submission.score is not None:
                    project_percentages.append(
                        submission.score / project.max_score * 100)
                project_cells.append({
                    'status': 'evaluated', 'score': submission.score, 'max_score': project.max_score,
                    'url_name': 'evaluate_submission', 'obj_id': submission.id,
                })

        activity_average = (
            sum(activity_percentages) / len(activity_percentages)
            if activity_percentages else None)
        project_average = (
            sum(project_percentages) / len(project_percentages)
            if project_percentages else None)

        if activity_average is not None and project_average is not None:
            average = (
                activity_average * subject.activity_weight
                + project_average * subject.project_weight) / 100
        elif activity_average is not None:
            average = activity_average
        elif project_average is not None:
            average = project_average
        else:
            average = None

        total_items = len(activity_cells) + len(project_cells)
        incomplete_items = sum(
            1 for cell in activity_cells + project_cells
            if cell['status'] in ('not_submitted', 'pending'))
        missing_work_ratio = (
            incomplete_items / total_items if total_items else 0)

        low_average = average is not None and average < subject.at_risk_threshold
        missing_too_much = total_items > 0 and missing_work_ratio > 0.5

        if low_average and missing_too_much:
            at_risk_reason = 'Low average and incomplete work'
        elif low_average:
            at_risk_reason = 'Low average'
        elif missing_too_much:
            at_risk_reason = 'Incomplete work'
        else:
            at_risk_reason = None

        rows.append({
            'student': student, 'activity_cells': activity_cells,
            'project_cells': project_cells, 'average': average,
            'activity_average': activity_average,
            'at_risk_reason': at_risk_reason,
        })

    ranked = sorted(
        (r for r in rows if r['average'] is not None),
        key=lambda r: r['average'], reverse=True)
    rank = 0
    previous_average = None
    for i, row in enumerate(ranked, start=1):
        if row['average'] != previous_average:
            rank = i
            previous_average = row['average']
        row['rank'] = rank
    for row in rows:
        row.setdefault('rank', None)

    return {
        'activities': activities, 'projects': projects, 'rows': rows,
        'column_count': activities.count() + projects.count(),
    }


@login_required
def gradesheet_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    data = build_gradesheet_data(subject)
    pending_count = ActivityCompletion.objects.filter(
        activity__topic__lesson_plan__subject=subject, graded=False).count()
    return render(request, 'tracker/gradesheet.html', {
        'subject': subject, 'activities': data['activities'],
        'projects': data['projects'], 'rows': data['rows'],
        'column_count': data['column_count'],
        'weights_form': SubjectWeightsForm(instance=subject),
        'show_teacher_controls': True,
        'pending_count': pending_count,
    })


@login_required
def my_gradesheet_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, students=request.user)
    students = subject.students.all().order_by(
    'last_name', 'first_name', 'username')
    activities = Activity.objects.filter(
        topic__lesson_plan__subject=subject).select_related('topic').order_by('deadline')
    projects = subject.projects.all().order_by('deadline')

    activity_completions = ActivityCompletion.objects.filter(
        activity__in=activities)
    completion_map = {
        (c.student_id, c.activity_id): c for c in activity_completions}

    submissions = ProjectSubmission.objects.filter(project__in=projects)
    submission_map = {
        (sub.student_id, sub.project_id): sub for sub in submissions}

    all_rows = [
        _build_gradesheet_row(subject, student, activities, projects,
                               completion_map, submission_map, is_teacher=False)
        for student in students
    ]
    _rank_gradesheet_rows(all_rows)
    own_row = next(
        (r for r in all_rows if r['student'].id == request.user.id), None)

    return render(request, 'tracker/gradesheet.html', {
        'subject': subject, 'activities': activities, 'projects': projects,
        'rows': [own_row] if own_row else [],
        'column_count': activities.count() + projects.count(),
        'show_teacher_controls': False,
    })

@login_required
def subject_analytics(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    student_count = subject.students.count()

    activities = Activity.objects.filter(topic__lesson_plan__subject=subject).order_by('deadline')
    projects = subject.projects.all().order_by('deadline')

    completion_labels = []
    completion_rates = []
    for activity in activities:
        submitted = ActivityCompletion.objects.filter(activity=activity).count()
        rate = round(submitted / student_count * 100) if student_count else 0
        completion_labels.append(activity.title)
        completion_rates.append(rate)
    for project in projects:
        submitted = ProjectSubmission.objects.filter(project=project).count()
        rate = round(submitted / student_count * 100) if student_count else 0
        completion_labels.append(project.title)
        completion_rates.append(rate)

    score_items = []
    for activity in activities:
        graded = ActivityCompletion.objects.filter(activity=activity, graded=True)
        if graded.exists() and activity.max_score:
            avg_pct = sum(c.score / activity.max_score * 100 for c in graded) / graded.count()
            score_items.append({'label': activity.title, 'deadline': activity.deadline, 'avg': round(avg_pct, 1)})
    for project in projects:
        graded = ProjectSubmission.objects.filter(project=project, evaluated=True, score__isnull=False)
        if graded.exists() and project.max_score:
            avg_pct = sum(s.score / project.max_score * 100 for s in graded) / graded.count()
            score_items.append({'label': project.title, 'deadline': project.deadline, 'avg': round(avg_pct, 1)})
    score_items.sort(key=lambda x: x['deadline'] or date.max)

    context = {
        'subject': subject,
        'completion_chart_data': {'labels': completion_labels, 'rates': completion_rates},
        'score_chart_data': {'labels': [i['label'] for i in score_items], 'averages': [i['avg'] for i in score_items]},
        'has_completion_data': bool(completion_labels),
        'has_score_data': bool(score_items),
    }
    return render(request, 'tracker/subject_analytics.html', context)

@login_required
def my_subject_analytics(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, students=request.user)

    activities = Activity.objects.filter(topic__lesson_plan__subject=subject).order_by('deadline')
    projects = subject.projects.all().order_by('deadline')

    score_items = []
    for activity in activities:
        completion = ActivityCompletion.objects.filter(
            activity=activity, student=request.user, graded=True).first()
        if completion and completion.score is not None and activity.max_score:
            pct = completion.score / activity.max_score * 100
            score_items.append({'label': activity.title, 'deadline': activity.deadline, 'score': round(pct, 1)})
    for project in projects:
        submission = ProjectSubmission.objects.filter(
            project=project, student=request.user, evaluated=True, score__isnull=False).first()
        if submission and project.max_score:
            pct = submission.score / project.max_score * 100
            score_items.append({'label': project.title, 'deadline': project.deadline, 'score': round(pct, 1)})
    score_items.sort(key=lambda x: x['deadline'] or date.max)

    context = {
        'subject': subject,
        'score_chart_data': {'labels': [i['label'] for i in score_items], 'scores': [i['score'] for i in score_items]},
        'has_score_data': bool(score_items),
    }
    return render(request, 'tracker/my_subject_analytics.html', context)

@login_required
def update_grade_weights(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    if request.method == 'POST':
        form = SubjectWeightsForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    return redirect('gradesheet_view', subject_id=subject.id)


def manage_students(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    if subject.teacher.profile.mode == 'personal':
        return redirect('lesson_plan_view', subject_id=subject.id)

    teacher_school = subject.teacher.profile.school
    query = request.GET.get('q', '')
    results = []
    if query and teacher_school:
        results = User.objects.filter(
            profile__role='student', profile__mode='professional',
            profile__school=teacher_school, username__icontains=query
        ).exclude(id__in=subject.students.values_list('id', flat=True))
    return render(request, 'tracker/manage_students.html', {
        'subject': subject, 'query': query, 'results': results,
        'no_school': not teacher_school,
    })

def class_skill_summary(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    students = subject.students.select_related('profile__course').order_by(
        'profile__course__name', 'username')

    student_skills = StudentSkill.objects.filter(
        student__in=students, skill__category__in=['course', 'general']
    ).select_related('skill', 'skill__course')

    skill_map = {(ss.student_id, ss.skill_id): ss for ss in student_skills}

    present_skill_ids = {ss.skill_id for ss in student_skills}
    relevant_skills = [s for s in get_relevant_skills() if s.id in present_skill_ids]
    general_skills = [s for s in relevant_skills if s.category == 'general']
    course_skills_pool = [s for s in relevant_skills if s.category == 'course']

    def skill_average(skill):
        levels = [ss.level for (
            sid, skid), ss in skill_map.items() if skid == skill.id]
        return round(sum(levels) / len(levels), 1) if levels else None

    general_averages = [skill_average(s) for s in general_skills]
    

    def build_cells(student, skill_list, averages):
        cells = []
        for skill, avg in zip(skill_list, averages):
            ss = skill_map.get((student.id, skill.id))
            level = ss.level if ss else None
            cells.append({
                'level': level,
                'behind': level is not None and avg is not None and level <= avg - 1,
            })
        return cells

    groups = []
    for student in students:
        course = student.profile.course
        course_name = course.name if course else 'No Course Assigned'
        if not groups or groups[-1]['course_name'] != course_name:
            group_course_skills = [
                s for s in course_skills_pool if course and s.course_id == course.id]
            groups.append({
                'course_name': course_name,
                'course_skills': group_course_skills,
                'course_averages': [skill_average(s) for s in group_course_skills],
                'rows': [],
            })
        group = groups[-1]
        group['rows'].append({
            'student': student,
            'general_cells': build_cells(student, general_skills, general_averages),
            'course_cells': build_cells(student, group['course_skills'], group['course_averages']),
        })

    has_any_skills = bool(general_skills) or any(g['course_skills'] for g in groups)

    return render(request, 'tracker/class_skill_summary.html', {
        'subject': subject,
        'general_skills': general_skills, 'general_averages': general_averages,
        'groups': groups, 'has_any_skills': has_any_skills,
    })


@login_required
def add_student_to_subject(request, subject_id, student_id):
    subject = get_object_or_404(Subject, id=subject_id)
    student = get_object_or_404(
        User, id=student_id, profile__role='student', profile__mode='professional')
    if subject.teacher.profile.school and student.profile.school == subject.teacher.profile.school:
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
    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = TaskActivityForm(
            request.POST, user=request.user, relevant_skills=relevant_skills)
        if form.is_valid():
            form.save()
            return redirect('task_list')
    else:
        form = TaskActivityForm(
            user=request.user, relevant_skills=relevant_skills)
    return render(request, 'tracker/add_task_activity.html', {
        'form': form, 'skill_groups': skill_groups_for_picker(relevant_skills),
    })


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

def skill_applies_to_student(skill, student):
    if skill is None:
        return False
    if skill.category != 'course':
        return True 
    profile = getattr(student, 'profile', None)
    student_course_id = getattr(profile, 'course_id', None)
    return skill.course_id is not None and skill.course_id == student_course_id