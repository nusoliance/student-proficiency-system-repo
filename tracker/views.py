from django.shortcuts import get_object_or_404
from .models import Subject, SubjectMeetingDay, LessonPlan, Topic, Activity, ActivityCompletion, Assignment, AssignmentCompletion, Project, ProjectSubmission, SkillAward, PersonalTask, Skill, TopicDocument, TopicImage, Quiz, QuizSkillWeight, QuizCompletion, QuizSkillAward, Exam, ExamSkillWeight, ExamCompletion, ExamSkillAward, DAY_CHOICES
from .forms import SubjectForm, SubjectCustomizeForm, TopicForm, ActivityForm, ProjectForm, SubmissionForm, SkillAwardForm, ManageStudentsForm, ActivityCompletionForm, AssignmentForm, AssignmentCompletionForm, GradeAssignmentForm, TaskActivityForm, TaskProjectForm, PersonalTaskForm, GradeActivityForm, GradeProjectForm, SubjectWeightsForm, TopicDocumentForm, TopicImageForm, QuizForm, QuizSkillWeightForm, GradeQuizForm, ExamForm, ExamSkillWeightForm, GradeExamForm
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import calendar as cal_module
import os
from django.db.models import Q, Case, When, Value, IntegerField, Sum
from avatar.models import Skill, StudentSkill
from django.contrib import messages
from datetime import date

def _points_for_score(activity, score):
    if score is None:
        return 0, 0, 0
    temp = ActivityCompletion(activity=activity, score=score)
    return temp.main_points, temp.secondary_points, temp.tertiary_points


def _adjust_activity_skill_points(completion, activity, score, sign):
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


def _points_for_assignment_score(assignment, score):
    if score is None:
        return 0, 0, 0
    temp = AssignmentCompletion(assignment=assignment, score=score)
    return temp.main_points, temp.secondary_points, temp.tertiary_points


def _adjust_assignment_skill_points(completion, assignment, score, sign):
    main, secondary, tertiary = _points_for_assignment_score(assignment, score)
    awards = [(assignment.skill_main, main)]
    if assignment.skill_secondary:
        awards.append((assignment.skill_secondary, secondary))
    if assignment.skill_tertiary:
        awards.append((assignment.skill_tertiary, tertiary))
    for skill, points in awards:
        if not skill_applies_to_student(skill, completion.student):
            continue
        student_skill, created = completion.student.skills.get_or_create(skill=skill)
        student_skill.points = max(0, student_skill.points + sign * points)
        student_skill.save()


def _award_assignment_skill_points(completion, assignment):
    _adjust_assignment_skill_points(completion, assignment, completion.score, sign=1)


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


def save_subject_meeting_days(subject, cleaned_data):
    subject.meeting_days.all().delete()
    delivery_mode = cleaned_data.get('delivery_mode')
    days = cleaned_data.get('days') or []
    onsite_days = set(cleaned_data.get('onsite_days') or [])
    for day in days:
        if delivery_mode == 'onsite':
            mode = 'onsite'
        elif delivery_mode == 'hybrid':
            mode = 'onsite' if day in onsite_days else 'online'
        else:
            mode = 'online'
        SubjectMeetingDay.objects.create(subject=subject, day=day, mode=mode)


@login_required
def add_subject(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST, user=request.user)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.teacher = request.user
            subject.save()
            form.save_m2m()
            save_subject_meeting_days(subject, form.cleaned_data)
            if request.user.profile.mode == 'personal':
                subject.students.add(request.user)
            LessonPlan.objects.create(subject=subject)
            return redirect('subject_list')
    else:
        form = SubjectForm(user=request.user)
    return render(request, 'tracker/add_subject.html', {'form': form})


@login_required
def customize_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    existing_days = {d.day: d.mode for d in subject.meeting_days.all()}
    initial = {
        'days': list(existing_days.keys()),
        'onsite_days': [day for day, mode in existing_days.items() if mode == 'onsite'],
    }
    if request.method == 'POST':
        form = SubjectCustomizeForm(request.POST, instance=subject, initial=initial)
        if form.is_valid():
            subject = form.save()
            save_subject_meeting_days(subject, form.cleaned_data)
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        form = SubjectCustomizeForm(instance=subject, initial=initial)
    return render(request, 'tracker/customize_subject.html', {
        'subject': subject, 'form': form,
    })


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
def edit_topic(request, topic_id):
    topic = get_object_or_404(
        Topic, id=topic_id, lesson_plan__subject__teacher=request.user)
    subject = topic.lesson_plan.subject
    if request.method == 'POST':
        form = TopicForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        form = TopicForm(instance=topic)
    return render(request, 'tracker/edit_topic.html', {
        'form': form, 'subject': subject, 'topic': topic,
    })

@login_required
def topic_detail(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    is_manager = subject.teacher == request.user
    return render(request, 'tracker/topic_detail.html', {
        'topic': topic, 'subject': subject, 'is_manager': is_manager,
    })


@login_required
def toggle_semester_split(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    if subject.teacher == request.user and request.method == 'POST':
        new_value = 'divide_by_semester' in request.POST
        if new_value and not subject.divide_by_semester:
            subject.midterm_activity_weight = subject.activity_weight // 2
            subject.final_activity_weight = subject.activity_weight - subject.midterm_activity_weight
            subject.midterm_quiz_weight = subject.quiz_weight // 2
            subject.final_quiz_weight = subject.quiz_weight - subject.midterm_quiz_weight
            subject.midterm_assignment_weight = subject.assignment_weight // 2
            subject.final_assignment_weight = subject.assignment_weight - subject.midterm_assignment_weight
        elif not new_value and subject.divide_by_semester:
            subject.activity_weight = subject.midterm_activity_weight + subject.final_activity_weight
            subject.quiz_weight = subject.midterm_quiz_weight + subject.final_quiz_weight
            subject.assignment_weight = subject.midterm_assignment_weight + subject.final_assignment_weight
        subject.divide_by_semester = new_value
        subject.save()
    return redirect('topic_detail', topic_id=topic.id)


@login_required
def topic_activities_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    is_manager = subject.teacher == request.user

    term = request.GET.get('term')
    activities = topic.activities.all()
    if subject.divide_by_semester and term in ('midterm', 'final'):
        activities = activities.filter(term=term)

    activity_ids = activities.values_list('id', flat=True)
    completed_activity_ids = set(
        ActivityCompletion.objects.filter(
            student=request.user, activity_id__in=activity_ids).values_list('activity_id', flat=True)
    )
    term_label = {'midterm': 'Midterm ', 'final': 'Final '}.get(term, '')
    return render(request, 'tracker/topic_activities.html', {
        'topic': topic, 'subject': subject, 'is_manager': is_manager,
        'activities': activities, 'term': term, 'term_label': term_label,
        'completed_activity_ids': completed_activity_ids,
    })

@login_required
def topic_assignments_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    is_manager = subject.teacher == request.user

    term = request.GET.get('term')
    assignments = topic.assignments.all()
    if subject.divide_by_semester and term in ('midterm', 'final'):
        assignments = assignments.filter(term=term)

    assignment_ids = assignments.values_list('id', flat=True)
    completed_assignment_ids = set(
        AssignmentCompletion.objects.filter(
            student=request.user, assignment_id__in=assignment_ids).values_list('assignment_id', flat=True)
    )
    term_label = {'midterm': 'Midterm ', 'final': 'Final '}.get(term, '')
    return render(request, 'tracker/topic_assignments.html', {
        'topic': topic, 'subject': subject, 'is_manager': is_manager,
        'assignments': assignments, 'term': term, 'term_label': term_label,
        'completed_assignment_ids': completed_assignment_ids,
    })


@login_required
def topic_quizzes_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    is_manager = subject.teacher == request.user

    term = request.GET.get('term')
    quizzes = topic.quizzes.all()
    if subject.divide_by_semester and term in ('midterm', 'final'):
        quizzes = quizzes.filter(term=term)

    completions_by_quiz = {
        c.quiz_id: c for c in QuizCompletion.objects.filter(quiz__in=quizzes, student=request.user)
    }
    quiz_data = [{'quiz': q, 'completion': completions_by_quiz.get(q.id)} for q in quizzes]
    term_label = {'midterm': 'Midterm ', 'final': 'Final '}.get(term, '')
    return render(request, 'tracker/topic_quizzes.html', {
        'topic': topic, 'subject': subject, 'is_manager': is_manager, 'quiz_data': quiz_data,
        'term': term, 'term_label': term_label,
    })

@login_required
def add_quiz(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    if subject.teacher != request.user:
        return redirect('topic_quizzes', topic_id=topic.id)
    if request.method == 'POST':
        form = QuizForm(request.POST, request.FILES)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.topic = topic
            quiz.save()
            return redirect('add_quiz_skill', quiz_id=quiz.id)
    else:
        initial = {}
        if request.GET.get('term') in ('midterm', 'final'):
            initial['term'] = request.GET.get('term')
        form = QuizForm(initial=initial)
    return render(request, 'tracker/add_quiz.html', {'form': form, 'topic': topic, 'subject': subject})


@login_required
def add_quiz_skill_weight(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    subject = quiz.topic.lesson_plan.subject
    if subject.teacher != request.user:
        return redirect('topic_quizzes', topic_id=quiz.topic.id)

    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = QuizSkillWeightForm(request.POST, quiz=quiz, relevant_skills=relevant_skills)
        if form.is_valid():
            weight = form.save(commit=False)
            weight.quiz = quiz
            weight.save()
            return redirect('add_quiz_skill', quiz_id=quiz.id)
    else:
        form = QuizSkillWeightForm(quiz=quiz, relevant_skills=relevant_skills)

    total_percentage = quiz.skill_weights.aggregate(total=Sum('percentage'))['total'] or 0
    return render(request, 'tracker/add_quiz_skill.html', {
        'quiz': quiz, 'form': form, 'skills': relevant_skills, 'total_percentage': total_percentage,
    })


@login_required
def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    subject = quiz.topic.lesson_plan.subject
    is_owner = subject.teacher == request.user
    is_personal = request.user.profile.mode == 'personal'

    if is_owner and is_personal:
        completion = QuizCompletion.objects.filter(quiz=quiz, student=request.user).first()
        if request.method == 'POST' and not completion:
            completion = QuizCompletion.objects.create(quiz=quiz, student=request.user)
            return redirect('grade_quiz_completion', completion_id=completion.id)
        return render(request, 'tracker/quiz_detail_personal.html', {'quiz': quiz, 'completion': completion})

    if is_owner:
        completions = quiz.completions.select_related('student').all()
        pending_count = completions.filter(graded=False).count()
        return render(request, 'tracker/quiz_detail_teacher.html', {
            'quiz': quiz, 'completions': completions, 'pending_count': pending_count,
        })

    completion = QuizCompletion.objects.filter(quiz=quiz, student=request.user).first()
    if request.method == 'POST' and not completion:
        completion = QuizCompletion.objects.create(quiz=quiz, student=request.user)
    return render(request, 'tracker/quiz_detail.html', {'quiz': quiz, 'completion': completion})


@login_required
def grade_quiz_completion(request, completion_id):
    completion = get_object_or_404(QuizCompletion, id=completion_id)
    quiz = completion.quiz
    if quiz.topic.lesson_plan.subject.teacher != request.user:
        return redirect('home')

    if request.method == 'POST' and not completion.graded:
        form = GradeQuizForm(request.POST, instance=completion, max_score=quiz.max_score)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()
            total_points = completion.total_points
            for weight in quiz.skill_weights.all():
                delta = total_points * weight.percentage // 100
                student_skill, created = completion.student.skills.get_or_create(skill=weight.skill)
                points_before = student_skill.points
                points_after = max(0, points_before + delta)
                student_skill.points = points_after
                student_skill.save()
                QuizSkillAward.objects.create(
                    completion=completion, skill=weight.skill, delta=delta,
                    points_before=points_before, points_after=points_after,
                )
            return redirect('grade_quiz_completion', completion_id=completion.id)
    else:
        form = GradeQuizForm(instance=completion, max_score=quiz.max_score)

    return render(request, 'tracker/grade_quiz_completion.html', {
        'quiz': quiz, 'completion': completion, 'form': form,
        'pool': quiz.max_score // 2,
        'total_points': completion.total_points if completion.graded else None,
    })


@login_required
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, topic__lesson_plan__subject__teacher=request.user)
    topic_id = quiz.topic.id
    if request.method == 'POST':
        quiz.delete()
        return redirect('topic_quizzes', topic_id=topic_id)
    return render(request, 'tracker/confirm_delete.html', {
        'object_name': quiz.title, 'cancel_url': 'topic_quizzes', 'cancel_arg': topic_id,
    })

@login_required
def topic_documents_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    is_manager = subject.teacher == request.user

    if request.method == 'POST' and is_manager:
        form = TopicDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.topic = topic
            doc.save()
            return redirect('topic_documents', topic_id=topic.id)
    else:
        form = TopicDocumentForm()

    documents = list(topic.topic_documents.all())
    return render(request, 'tracker/topic_documents.html', {
        'topic': topic, 'subject': subject, 'is_manager': is_manager,
        'documents': documents, 'form': form,
    })
DOCUMENT_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}


@login_required
def document_view(request, document_id):
    document = get_object_or_404(TopicDocument, id=document_id)
    topic = document.topic
    subject = topic.lesson_plan.subject
    ext = os.path.splitext(document.document.name)[1].lower()
    if ext == '.pdf':
        preview_type = 'pdf'
    elif ext in DOCUMENT_IMAGE_EXTS:
        preview_type = 'image'
    elif ext == '.docx':
        preview_type = 'docx'
    else:
        preview_type = 'none'
    return render(request, 'tracker/document_view.html', {
        'document': document, 'topic': topic, 'subject': subject,
        'preview_type': preview_type,
    })


@login_required
def topic_images_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    is_manager = subject.teacher == request.user

    if request.method == 'POST' and is_manager:
        form = TopicImageForm(request.POST, request.FILES)
        if form.is_valid():
            img = form.save(commit=False)
            img.topic = topic
            img.save()
            return redirect('topic_images', topic_id=topic.id)
    else:
        form = TopicImageForm()

    images = topic.topic_images.all()
    return render(request, 'tracker/topic_images.html', {
        'topic': topic, 'subject': subject, 'is_manager': is_manager,
        'images': images, 'form': form,
    })

@login_required
def add_activity(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = ActivityForm(request.POST, relevant_skills=relevant_skills)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.topic = topic
            activity.save()
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        initial = {}
        if request.GET.get('term') in ('midterm', 'final'):
            initial['term'] = request.GET.get('term')
        form = ActivityForm(relevant_skills=relevant_skills, initial=initial)
    return render(request, 'tracker/add_activity.html', {
        'form': form, 'topic': topic, 'subject': subject,
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
def add_assignment(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    subject = topic.lesson_plan.subject
    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = AssignmentForm(request.POST, relevant_skills=relevant_skills)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.topic = topic
            assignment.save()
            return redirect('lesson_plan_view', subject_id=subject.id)
    else:
        initial = {}
        if request.GET.get('term') in ('midterm', 'final'):
            initial['term'] = request.GET.get('term')
        form = AssignmentForm(relevant_skills=relevant_skills, initial=initial)
    return render(request, 'tracker/add_assignment.html', {
        'form': form, 'topic': topic, 'subject': subject,
        'skill_groups': skill_groups_for_picker(relevant_skills),
    })


@login_required
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    subject = assignment.topic.lesson_plan.subject
    is_owner = subject.teacher == request.user
    is_personal = request.user.profile.mode == 'personal'

    if is_owner and is_personal:
        completion = AssignmentCompletion.objects.filter(
            assignment=assignment, student=request.user).first()
        if request.method == 'POST' and not completion:
            form = AssignmentCompletionForm(request.POST, request.FILES)
            if form.is_valid():
                completion = form.save(commit=False)
                completion.assignment = assignment
                completion.student = request.user
                completion.save()
                return redirect('assignment_detail', assignment_id=assignment.id)
        else:
            form = AssignmentCompletionForm()
        return render(request, 'tracker/assignment_detail_personal.html', {'assignment': assignment, 'completion': completion, 'form': form})

    if is_owner:
        completions = assignment.completions.select_related('student').all()
        return render(request, 'tracker/assignment_detail_teacher.html', {'assignment': assignment, 'completions': completions})

    completion = AssignmentCompletion.objects.filter(
        assignment=assignment, student=request.user).first()
    if request.method == 'POST' and not completion:
        form = AssignmentCompletionForm(request.POST, request.FILES)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.assignment = assignment
            completion.student = request.user
            completion.save()
            return redirect('assignment_detail', assignment_id=assignment.id)
    else:
        form = AssignmentCompletionForm()
    return render(request, 'tracker/assignment_detail.html', {'assignment': assignment, 'completion': completion, 'form': form})


@login_required
def grade_assignment_completion(request, completion_id):
    completion = get_object_or_404(AssignmentCompletion, id=completion_id)
    assignment = completion.assignment
    if assignment.topic.lesson_plan.subject.teacher != request.user:
        return redirect('home')

    if request.method == 'POST':
        was_graded = completion.graded
        old_score = completion.score

        form = GradeAssignmentForm(
            request.POST, instance=completion, max_score=assignment.max_score)
        if form.is_valid():
            if was_graded:
                _adjust_assignment_skill_points(completion, assignment, old_score, sign=-1)
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()

            _award_assignment_skill_points(completion, assignment)
            messages.success(request, 'Grade saved.')
            return redirect('grade_assignment_completion', completion_id=completion.id)
    else:
        form = GradeAssignmentForm(
            instance=completion, max_score=assignment.max_score)

    show_form = not completion.graded or request.GET.get('edit') == '1'
    return render(request, 'tracker/grade_assignment_completion.html', {
        'completion': completion, 'assignment': assignment, 'form': form,
        'show_form': show_form,
    })

@login_required
def grade_assignment_queue(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if assignment.topic.lesson_plan.subject.teacher != request.user:
        return redirect('home')

    pending = assignment.completions.filter(graded=False).select_related('student').order_by('completed_at')
    completion = pending.first()

    if not completion:
        return render(request, 'tracker/grade_assignment_queue_done.html', {
            'assignment': assignment, 'total_graded': assignment.completions.filter(graded=True).count(),
        })

    remaining_count = pending.count()

    if request.method == 'POST':
        form = GradeAssignmentForm(request.POST, instance=completion, max_score=assignment.max_score)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()
            _award_assignment_skill_points(completion, assignment)
            return redirect('grade_assignment_queue', assignment_id=assignment.id)
    else:
        form = GradeAssignmentForm(instance=completion, max_score=assignment.max_score)

    return render(request, 'tracker/grade_assignment_queue.html', {
        'assignment': assignment, 'completion': completion, 'form': form, 'remaining_count': remaining_count,
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


EXAM_TYPE_ORDER = ['prelim', 'midterm', 'prefinal', 'final']


def build_gradesheet_data(subject, is_teacher=True):
    students = subject.students.all().order_by(
    'last_name', 'first_name', 'username')
    divide = subject.divide_by_semester
    activities = Activity.objects.filter(
        topic__lesson_plan__subject=subject).select_related('topic').order_by('deadline')
    quizzes = Quiz.objects.filter(
        topic__lesson_plan__subject=subject).select_related('topic').order_by('deadline')
    assignments = Assignment.objects.filter(
        topic__lesson_plan__subject=subject).select_related('topic').order_by('deadline')
    midterm_activities = [a for a in activities if a.term != 'final']
    final_activities = [a for a in activities if a.term == 'final']
    midterm_quizzes = [q for q in quizzes if q.term != 'final']
    final_quizzes = [q for q in quizzes if q.term == 'final']
    midterm_assignments = [a for a in assignments if a.term != 'final']
    final_assignments = [a for a in assignments if a.term == 'final']
    exams_by_type = {e.exam_type: e for e in subject.exams.all()}
    exam_list = [exams_by_type.get(t) for t in EXAM_TYPE_ORDER]
    projects = subject.projects.all().order_by('deadline')

    activity_completions = ActivityCompletion.objects.filter(
        activity__in=activities)
    completion_map = {
        (c.student_id, c.activity_id): c for c in activity_completions}

    quiz_completions = QuizCompletion.objects.filter(quiz__in=quizzes)
    quiz_completion_map = {
        (c.student_id, c.quiz_id): c for c in quiz_completions}

    assignment_completions = AssignmentCompletion.objects.filter(
        assignment__in=assignments)
    assignment_completion_map = {
        (c.student_id, c.assignment_id): c for c in assignment_completions}

    existing_exams = [e for e in exam_list if e is not None]
    exam_completions = ExamCompletion.objects.filter(exam__in=existing_exams)
    exam_completion_map = {
        (c.student_id, c.exam_id): c for c in exam_completions}

    submissions = ProjectSubmission.objects.filter(project__in=projects)
    submission_map = {
        (sub.student_id, sub.project_id): sub for sub in submissions}

    rows = []
    for student in students:
        activity_cells = []
        quiz_cells = []
        assignment_cells = []
        exam_cells = []
        project_cells = []
        activity_percentages = []
        quiz_percentages = []
        quiz_passing_percentages = []
        assignment_percentages = []
        project_percentages = []
        exam_pcts = {}
        activity_cell_by_id = {}
        activity_pct_by_id = {}
        quiz_cell_by_id = {}
        quiz_pct_by_id = {}
        quiz_passing_pct_by_id = {}
        assignment_cell_by_id = {}
        assignment_pct_by_id = {}

        for activity in activities:
            completion = completion_map.get((student.id, activity.id))
            if completion is None:
                cell = {
                    'status': 'not_submitted', 'score': None, 'max_score': activity.max_score,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                }
            elif not completion.graded:
                cell = {
                    'status': 'pending', 'score': None, 'max_score': activity.max_score,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                }
            else:
                if activity.max_score:
                    pct = completion.score / activity.max_score * 100
                    activity_percentages.append(pct)
                    activity_pct_by_id[activity.id] = pct
                cell = {
                    'status': 'evaluated', 'score': completion.score, 'max_score': activity.max_score,
                    'url_name': 'activity_detail', 'obj_id': activity.id,
                }
            activity_cells.append(cell)
            activity_cell_by_id[activity.id] = cell

        for quiz in quizzes:
            completion = quiz_completion_map.get((student.id, quiz.id))
            if completion is None:
                cell = {
                    'status': 'not_submitted', 'score': None, 'max_score': quiz.max_score,
                    'url_name': 'quiz_detail', 'obj_id': quiz.id,
                }
            elif not completion.graded:
                cell = {
                    'status': 'pending', 'score': None, 'max_score': quiz.max_score,
                    'url_name': 'quiz_detail', 'obj_id': quiz.id,
                }
            else:
                below_passing = completion.score < quiz.passing_score
                if quiz.max_score:
                    pct = completion.score / quiz.max_score * 100
                    quiz_percentages.append(pct)
                    quiz_passing_percentages.append(quiz.passing_percentage)
                    quiz_pct_by_id[quiz.id] = pct
                    quiz_passing_pct_by_id[quiz.id] = quiz.passing_percentage
                cell = {
                    'status': 'evaluated', 'score': completion.score, 'max_score': quiz.max_score,
                    'url_name': 'quiz_detail', 'obj_id': quiz.id,
                    'below_passing': below_passing,
                }
            quiz_cells.append(cell)
            quiz_cell_by_id[quiz.id] = cell

        for assignment in assignments:
            completion = assignment_completion_map.get((student.id, assignment.id))
            if completion is None:
                cell = {
                    'status': 'not_submitted', 'score': None, 'max_score': assignment.max_score,
                    'url_name': 'assignment_detail', 'obj_id': assignment.id,
                }
            elif not completion.graded:
                cell = {
                    'status': 'pending', 'score': None, 'max_score': assignment.max_score,
                    'url_name': 'assignment_detail', 'obj_id': assignment.id,
                }
            else:
                if assignment.max_score:
                    pct = completion.score / assignment.max_score * 100
                    assignment_percentages.append(pct)
                    assignment_pct_by_id[assignment.id] = pct
                cell = {
                    'status': 'evaluated', 'score': completion.score, 'max_score': assignment.max_score,
                    'url_name': 'assignment_detail', 'obj_id': assignment.id,
                }
            assignment_cells.append(cell)
            assignment_cell_by_id[assignment.id] = cell

        for exam_type, exam in zip(EXAM_TYPE_ORDER, exam_list):
            if exam is None:
                exam_cells.append({'status': 'not_added'})
                continue
            completion = exam_completion_map.get((student.id, exam.id))
            if completion is None:
                exam_cells.append({
                    'status': 'not_submitted', 'score': None, 'max_score': exam.max_score,
                    'url_name': 'exam_detail', 'obj_id': exam.id,
                })
            elif not completion.graded:
                exam_cells.append({
                    'status': 'pending', 'score': None, 'max_score': exam.max_score,
                    'url_name': 'exam_detail', 'obj_id': exam.id,
                })
            else:
                below_passing = completion.score < exam.passing_score
                if exam.max_score:
                    exam_pcts[exam_type] = completion.score / exam.max_score * 100
                exam_cells.append({
                    'status': 'evaluated', 'score': completion.score, 'max_score': exam.max_score,
                    'url_name': 'exam_detail', 'obj_id': exam.id,
                    'below_passing': below_passing,
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
        quiz_average = (
            sum(quiz_percentages) / len(quiz_percentages)
            if quiz_percentages else None)
        quiz_average_below_passing = (
            quiz_average is not None
            and quiz_average < (sum(quiz_passing_percentages) / len(quiz_passing_percentages)))
        project_average = (
            sum(project_percentages) / len(project_percentages)
            if project_percentages else None)
        assignment_average = (
            sum(assignment_percentages) / len(assignment_percentages)
            if assignment_percentages else None)

        def term_avg(pct_by_id, term_items):
            pcts = [pct_by_id[item.id] for item in term_items if item.id in pct_by_id]
            return sum(pcts) / len(pcts) if pcts else None

        def term_quiz_avg_below_passing(term_avg_value, term_items):
            passing_pcts = [
                quiz_passing_pct_by_id[item.id] for item in term_items
                if item.id in quiz_passing_pct_by_id]
            if term_avg_value is None or not passing_pcts:
                return False
            return term_avg_value < (sum(passing_pcts) / len(passing_pcts))

        midterm_activity_avg = term_avg(activity_pct_by_id, midterm_activities)
        final_activity_avg = term_avg(activity_pct_by_id, final_activities)
        midterm_quiz_avg = term_avg(quiz_pct_by_id, midterm_quizzes)
        final_quiz_avg = term_avg(quiz_pct_by_id, final_quizzes)
        midterm_assignment_avg = term_avg(assignment_pct_by_id, midterm_assignments)
        final_assignment_avg = term_avg(assignment_pct_by_id, final_assignments)

        if divide:
            weighted_categories = [
                (midterm_activity_avg, subject.midterm_activity_weight),
                (final_activity_avg, subject.final_activity_weight),
                (midterm_quiz_avg, subject.midterm_quiz_weight),
                (final_quiz_avg, subject.final_quiz_weight),
                (midterm_assignment_avg, subject.midterm_assignment_weight),
                (final_assignment_avg, subject.final_assignment_weight),
                (exam_pcts.get('prelim'), subject.prelim_weight),
                (exam_pcts.get('midterm'), subject.midterm_weight),
                (exam_pcts.get('prefinal'), subject.prefinal_weight),
                (exam_pcts.get('final'), subject.final_weight),
                (project_average, subject.project_weight),
            ]
        else:
            weighted_categories = [
                (activity_average, subject.activity_weight),
                (quiz_average, subject.quiz_weight),
                (assignment_average, subject.assignment_weight),
                (exam_pcts.get('prelim'), subject.prelim_weight),
                (exam_pcts.get('midterm'), subject.midterm_weight),
                (exam_pcts.get('prefinal'), subject.prefinal_weight),
                (exam_pcts.get('final'), subject.final_weight),
                (project_average, subject.project_weight),
            ]
        present = [(avg, w) for avg, w in weighted_categories if avg is not None]
        if not present:
            average = None
        else:
            total_weight = sum(w for _, w in present)
            if total_weight > 0:
                average = sum(avg * w for avg, w in present) / total_weight
            else:
                average = sum(avg for avg, _ in present) / len(present)

        all_cells = activity_cells + quiz_cells + assignment_cells + project_cells + [
            c for c in exam_cells if c['status'] != 'not_added']
        total_items = len(all_cells)
        incomplete_items = sum(
            1 for cell in all_cells
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

        row = {
            'student': student, 'activity_cells': activity_cells,
            'quiz_cells': quiz_cells, 'exam_cells': exam_cells,
            'assignment_cells': assignment_cells,
            'project_cells': project_cells, 'average': average,
            'activity_average': activity_average,
            'quiz_average': quiz_average,
            'assignment_average': assignment_average,
            'quiz_average_below_passing': quiz_average_below_passing,
            'average_below_passing': average is not None and average < subject.at_risk_threshold,
            'at_risk_reason': at_risk_reason,
        }

        if divide:
            row.update({
                'midterm_activity_cells': [activity_cell_by_id[a.id] for a in midterm_activities],
                'final_activity_cells': [activity_cell_by_id[a.id] for a in final_activities],
                'midterm_activity_average': midterm_activity_avg,
                'final_activity_average': final_activity_avg,
                'midterm_quiz_cells': [quiz_cell_by_id[q.id] for q in midterm_quizzes],
                'final_quiz_cells': [quiz_cell_by_id[q.id] for q in final_quizzes],
                'midterm_quiz_average': midterm_quiz_avg,
                'final_quiz_average': final_quiz_avg,
                'midterm_quiz_average_below_passing': term_quiz_avg_below_passing(midterm_quiz_avg, midterm_quizzes),
                'final_quiz_average_below_passing': term_quiz_avg_below_passing(final_quiz_avg, final_quizzes),
                'midterm_assignment_cells': [assignment_cell_by_id[a.id] for a in midterm_assignments],
                'final_assignment_cells': [assignment_cell_by_id[a.id] for a in final_assignments],
                'midterm_assignment_average': midterm_assignment_avg,
                'final_assignment_average': final_assignment_avg,
            })

        rows.append(row)

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
        'activities': activities, 'quizzes': quizzes, 'assignments': assignments,
        'midterm_activities': midterm_activities, 'final_activities': final_activities,
        'midterm_quizzes': midterm_quizzes, 'final_quizzes': final_quizzes,
        'midterm_assignments': midterm_assignments, 'final_assignments': final_assignments,
        'divide_by_semester': divide,
        'exam_columns': list(zip(EXAM_TYPE_ORDER, exam_list)),
        'projects': projects, 'rows': rows,
        'column_count': (
            activities.count() + quizzes.count() + assignments.count()
            + len(existing_exams) + projects.count()),
    }


@login_required
def gradesheet_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, teacher=request.user)
    data = build_gradesheet_data(subject)
    pending_count = ActivityCompletion.objects.filter(
        activity__topic__lesson_plan__subject=subject, graded=False).count()
    return render(request, 'tracker/gradesheet.html', {
        'subject': subject, 'activities': data['activities'],
        'quizzes': data['quizzes'], 'assignments': data['assignments'], 'exam_columns': data['exam_columns'],
        'midterm_activities': data['midterm_activities'], 'final_activities': data['final_activities'],
        'midterm_quizzes': data['midterm_quizzes'], 'final_quizzes': data['final_quizzes'],
        'midterm_assignments': data['midterm_assignments'], 'final_assignments': data['final_assignments'],
        'divide_by_semester': data['divide_by_semester'],
        'projects': data['projects'], 'rows': data['rows'],
        'column_count': data['column_count'],
        'weights_form': SubjectWeightsForm(instance=subject, divide_by_semester=subject.divide_by_semester),
        'show_teacher_controls': True,
        'pending_count': pending_count,
    })


@login_required
def my_gradesheet_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id, students=request.user)
    data = build_gradesheet_data(subject, is_teacher=False)
    own_row = next(
        (r for r in data['rows'] if r['student'].id == request.user.id), None)
    
    weights_form = SubjectWeightsForm(instance=subject, divide_by_semester=subject.divide_by_semester)
    for field in weights_form.fields.values():
        field.disabled = True

    return render(request, 'tracker/gradesheet.html', {
        'subject': subject, 'activities': data['activities'],
        'quizzes': data['quizzes'], 'assignments': data['assignments'], 'exam_columns': data['exam_columns'],
        'midterm_activities': data['midterm_activities'], 'final_activities': data['final_activities'],
        'midterm_quizzes': data['midterm_quizzes'], 'final_quizzes': data['final_quizzes'],
        'midterm_assignments': data['midterm_assignments'], 'final_assignments': data['final_assignments'],
        'divide_by_semester': data['divide_by_semester'],
        'projects': data['projects'],
        'rows': [own_row] if own_row else [],
        'column_count': data['column_count'],
        'show_teacher_controls': False,
        'weights_form': weights_form,
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
        form = SubjectWeightsForm(request.POST, instance=subject, divide_by_semester=subject.divide_by_semester)
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


PERSONAL_TASK_WEEKDAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


def _next_weekly_task_deadline(current_deadline, weekly_days):
    days = weekly_days.split(',') if weekly_days else []
    if not days:
        return current_deadline + timedelta(days=7)
    for offset in range(1, 8):
        candidate = current_deadline + timedelta(days=offset)
        if PERSONAL_TASK_WEEKDAY_ORDER[candidate.weekday()] in days:
            return candidate
    return current_deadline + timedelta(days=7)


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

        if task.repeat != 'none' and task.deadline:
            if task.repeat == 'daily':
                next_deadline = task.deadline + timedelta(days=1)
            else:
                next_deadline = _next_weekly_task_deadline(task.deadline, task.weekly_days)
            PersonalTask.objects.create(
                student=task.student, title=task.title, no_deadline=False,
                deadline=next_deadline, start_time=task.start_time, end_time=task.end_time,
                difficulty=task.difficulty, importance=task.importance,
                skill_main=task.skill_main, skill_secondary=task.skill_secondary,
                skill_tertiary=task.skill_tertiary, repeat=task.repeat,
                weekly_days=task.weekly_days, notify=task.notify, completed=False,
            )
            messages.success(
                request,
                f'Nice work! "{task.title}" repeats, so the next one is scheduled for {next_deadline}.')
    return redirect('personal_task_detail', task_id=task.id)


@login_required
def personal_task_detail(request, task_id):
    task = get_object_or_404(PersonalTask, id=task_id, student=request.user)
    return render(request, 'tracker/personal_task_detail.html', {'task': task})


WEEK_CALENDAR_COLOR_PALETTE = [
    '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899',
    '#14B8A6', '#F97316', '#6366F1', '#84CC16', '#06B6D4',
]

RECURRING_EVENT_CUTOFF = date(2027, 1, 1)


def _subject_calendar_color(subject_id):
    return WEEK_CALENDAR_COLOR_PALETTE[subject_id % len(WEEK_CALENDAR_COLOR_PALETTE)]


def _format_12h(t):
    hour = t.hour % 12
    if hour == 0:
        hour = 12
    period = 'am' if t.hour < 12 else 'pm'
    if t.minute == 0:
        return f"{hour}{period}"
    return f"{hour}:{t.minute:02d}{period}"


def _event_size_class(height_px):
    if height_px < 22:
        return ' week-cal-event-xs'
    if height_px < 36:
        return ' week-cal-event-sm'
    if height_px < 55:
        return ' week-cal-event-md'
    return ''


@login_required
def calendar_hub_view(request):
    is_personal_student = request.user.profile.role == 'student' and request.user.profile.mode == 'personal'
    return render(request, 'tracker/calendar_hub.html', {
        'is_personal_student': is_personal_student,
    })


@login_required
def week_calendar_view(request):
    user = request.user
    today = timezone.now().date()

    week_start_param = request.GET.get('week_start')
    week_start = None
    if week_start_param:
        try:
            week_start = date.fromisoformat(week_start_param)
        except ValueError:
            week_start = None
    if week_start is None:
        week_start = today
    week_start = week_start - timedelta(days=week_start.weekday())
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    week_end = week_days[-1]

    subjects = Subject.objects.filter(
        Q(teacher=user) | Q(students=user)).distinct().prefetch_related('meeting_days')

    day_code_to_index = {code: i for i, (code, _) in enumerate(DAY_CHOICES)}

    timed_events = [[] for _ in range(7)]
    allday_events = [[] for _ in range(7)]

    if week_start <= RECURRING_EVENT_CUTOFF:
        for subject in subjects:
            if not subject.start_time or not subject.end_time:
                continue
            color = _subject_calendar_color(subject.id)
            time_label = f"{_format_12h(subject.start_time)} – {_format_12h(subject.end_time)}"
            for meeting_day in subject.meeting_days.all():
                idx = day_code_to_index.get(meeting_day.day)
                if idx is None:
                    continue
                start_minutes = subject.start_time.hour * 60 + subject.start_time.minute
                end_minutes = subject.end_time.hour * 60 + subject.end_time.minute
                duration = max(end_minutes - start_minutes, 15)
                if meeting_day.mode == 'onsite' and subject.room:
                    location_label = subject.room
                else:
                    location_label = 'Online'
                timed_events[idx].append({
                    'label': subject.name,
                    'time_label': time_label,
                    'location_label': location_label,
                    'top_px': start_minutes,
                    'height_px': duration,
                    'color': color,
                    'css_class': _event_size_class(duration),
                    'url_name': 'lesson_plan_view', 'obj_id': subject.id,
                })

    exams = Exam.objects.filter(
        subject__in=subjects, deadline__gte=week_start, deadline__lte=week_end)
    for exam in exams:
        idx = (exam.deadline - week_start).days
        allday_events[idx].append({
            'label': f"{exam.subject.name} — {exam.get_exam_type_display()}",
            'css_class': 'week-cal-exam-chip',
            'url_name': 'exam_detail', 'obj_id': exam.id,
        })

    TASK_COLOR = '#2563EB'
    TASK_MIN_DURATION = 15

    def _append_task_event(idx, task):
        if task.start_time and task.end_time:
            start_minutes = task.start_time.hour * 60 + task.start_time.minute
            end_minutes = task.end_time.hour * 60 + task.end_time.minute
            duration = max(end_minutes - start_minutes, TASK_MIN_DURATION)
            time_label = f"{_format_12h(task.start_time)} – {_format_12h(task.end_time)}"
            timed_events[idx].append({
                'label': task.title,
                'time_label': time_label,
                'location_label': 'Completed' if task.completed else 'Personal Task',
                'top_px': start_minutes,
                'height_px': duration,
                'color': TASK_COLOR,
                'css_class': _event_size_class(duration) + (' week-cal-event-done' if task.completed else ''),
                'url_name': 'personal_task_detail', 'obj_id': task.id,
            })
        else:
            allday_events[idx].append({
                'label': task.title,
                'css_class': 'week-cal-task-chip' + (' week-cal-chip-done' if task.completed else ''),
                'url_name': 'personal_task_detail', 'obj_id': task.id,
            })

    if user.profile.mode == 'personal':
        dated_tasks = PersonalTask.objects.filter(
            student=user, no_deadline=False,
            deadline__gte=week_start, deadline__lte=week_end)
        for task in dated_tasks:
            idx = (task.deadline - week_start).days
            _append_task_event(idx, task)

        if week_start <= RECURRING_EVENT_CUTOFF:
            recurring_tasks = PersonalTask.objects.filter(
                student=user, no_deadline=True, repeat__in=['daily', 'weekly'], completed=False)
            for task in recurring_tasks:
                if task.repeat == 'daily':
                    matching_days = range(7)
                else:
                    task_days = task.weekly_days.split(',') if task.weekly_days else []
                    matching_days = [
                        day_code_to_index[d] for d in task_days if d in day_code_to_index]
                for idx in matching_days:
                    if week_days[idx] > RECURRING_EVENT_CUTOFF:
                        continue
                    _append_task_event(idx, task)

    days_data = []
    for i, day in enumerate(week_days):
        days_data.append({
            'date': day, 'is_today': day == today,
            'timed_events': timed_events[i], 'allday_events': allday_events[i],
        })

    hours = []
    for h in range(24):
        hour_label = 12 if h % 12 == 0 else h % 12
        period = 'AM' if h < 12 else 'PM'
        hours.append(f"{hour_label} {period}")

    return render(request, 'tracker/week_calendar.html', {
        'days_data': days_data, 'hours': hours,
        'week_start': week_start, 'week_end': week_end,
        'today': today,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7),
        'this_week': today - timedelta(days=today.weekday()),
    })


@login_required
def tasks_calendar_view(request):
    user = request.user
    today = timezone.now().date()

    view_mode = request.GET.get('view', 'week')
    if view_mode not in ('week', 'month'):
        view_mode = 'week'

    subjects = Subject.objects.filter(
        Q(teacher=user) | Q(students=user)).distinct()
    is_personal_student = user.profile.role == 'student' and user.profile.mode == 'personal'

    context = {
        'view_mode': view_mode,
        'today': today,
        'is_personal_student': is_personal_student,
    }

    if view_mode == 'week':
        week_start_param = request.GET.get('week_start')
        week_start = None
        if week_start_param:
            try:
                week_start = date.fromisoformat(week_start_param)
            except ValueError:
                week_start = None
        if week_start is None:
            week_start = today
        week_start = week_start - timedelta(days=week_start.weekday())
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        week_end = week_days[-1]

        day_code_to_index = {code: i for i, (code, _) in enumerate(DAY_CHOICES)}

        timed_events = [[] for _ in range(7)]
        allday_events = [[] for _ in range(7)]

        activities = Activity.objects.filter(
            topic__lesson_plan__subject__in=subjects,
            deadline__gte=week_start, deadline__lte=week_end
        ).select_related('topic__lesson_plan__subject')
        for activity in activities:
            idx = (activity.deadline - week_start).days
            allday_events[idx].append({
                'label': f"{activity.topic.lesson_plan.subject.name}: {activity.title}",
                'css_class': 'week-cal-activity-chip',
                'url_name': 'activity_detail', 'obj_id': activity.id,
            })

        assignments = Assignment.objects.filter(
            topic__lesson_plan__subject__in=subjects,
            deadline__gte=week_start, deadline__lte=week_end
        ).select_related('topic__lesson_plan__subject')
        for assignment in assignments:
            idx = (assignment.deadline - week_start).days
            allday_events[idx].append({
                'label': f"{assignment.topic.lesson_plan.subject.name}: {assignment.title}",
                'css_class': 'week-cal-assignment-chip',
                'url_name': 'assignment_detail', 'obj_id': assignment.id,
            })

        quizzes = Quiz.objects.filter(
            topic__lesson_plan__subject__in=subjects,
            deadline__gte=week_start, deadline__lte=week_end
        ).select_related('topic__lesson_plan__subject')
        for quiz in quizzes:
            idx = (quiz.deadline - week_start).days
            allday_events[idx].append({
                'label': f"{quiz.topic.lesson_plan.subject.name}: {quiz.title}",
                'css_class': 'week-cal-quiz-chip',
                'url_name': 'quiz_detail', 'obj_id': quiz.id,
            })

        exams = Exam.objects.filter(
            subject__in=subjects, deadline__gte=week_start, deadline__lte=week_end
        ).select_related('subject')
        for exam in exams:
            idx = (exam.deadline - week_start).days
            allday_events[idx].append({
                'label': f"{exam.subject.name} — {exam.get_exam_type_display()}",
                'css_class': 'week-cal-exam-chip',
                'url_name': 'exam_detail', 'obj_id': exam.id,
            })

        projects = Project.objects.filter(
            subject__in=subjects, deadline__isnull=False,
            deadline__gte=week_start, deadline__lte=week_end
        ).select_related('subject')
        for project in projects:
            idx = (project.deadline - week_start).days
            allday_events[idx].append({
                'label': f"{project.subject.name}: {project.title}",
                'css_class': 'week-cal-project-chip',
                'url_name': 'project_detail', 'obj_id': project.id,
            })

        if is_personal_student:
            def _append_task_event(idx, task):
                if task.start_time and task.end_time:
                    start_minutes = task.start_time.hour * 60 + task.start_time.minute
                    end_minutes = task.end_time.hour * 60 + task.end_time.minute
                    duration = max(end_minutes - start_minutes, 15)
                    time_label = f"{_format_12h(task.start_time)} – {_format_12h(task.end_time)}"
                    timed_events[idx].append({
                        'label': task.title,
                        'time_label': time_label,
                        'location_label': 'Completed' if task.completed else 'Personal Task',
                        'top_px': start_minutes,
                        'height_px': duration,
                        'color': '#2563EB',
                        'css_class': _event_size_class(duration) + (' week-cal-event-done' if task.completed else ''),
                        'url_name': 'personal_task_detail', 'obj_id': task.id,
                    })
                else:
                    allday_events[idx].append({
                        'label': task.title,
                        'css_class': 'week-cal-task-chip' + (' week-cal-chip-done' if task.completed else ''),
                        'url_name': 'personal_task_detail', 'obj_id': task.id,
                    })

            dated_tasks = PersonalTask.objects.filter(
                student=user, no_deadline=False,
                deadline__gte=week_start, deadline__lte=week_end)
            for task in dated_tasks:
                idx = (task.deadline - week_start).days
                _append_task_event(idx, task)

            if week_start <= RECURRING_EVENT_CUTOFF:
                recurring_tasks = PersonalTask.objects.filter(
                    student=user, no_deadline=True, repeat__in=['daily', 'weekly'], completed=False)
                for task in recurring_tasks:
                    if task.repeat == 'daily':
                        matching_days = range(7)
                    else:
                        task_days = task.weekly_days.split(',') if task.weekly_days else []
                        matching_days = [
                            day_code_to_index[d] for d in task_days if d in day_code_to_index]
                    for idx in matching_days:
                        if week_days[idx] > RECURRING_EVENT_CUTOFF:
                            continue
                        _append_task_event(idx, task)

        days_data = []
        for i, day in enumerate(week_days):
            days_data.append({
                'date': day, 'is_today': day == today,
                'timed_events': timed_events[i], 'allday_events': allday_events[i],
            })

        hours = []
        for h in range(24):
            hour_label = 12 if h % 12 == 0 else h % 12
            period = 'AM' if h < 12 else 'PM'
            hours.append(f"{hour_label} {period}")

        context.update({
            'days_data': days_data, 'hours': hours,
            'week_start': week_start, 'week_end': week_end,
            'prev_week': week_start - timedelta(days=7),
            'next_week': week_start + timedelta(days=7),
            'this_week': today - timedelta(days=today.weekday()),
        })

    else:
        month_param = request.GET.get('month')
        month_date = None
        if month_param:
            try:
                y, m = month_param.split('-')
                month_date = date(int(y), int(m), 1)
            except (ValueError, IndexError):
                month_date = None
        if month_date is None:
            month_date = today.replace(day=1)

        c = cal_module.Calendar(firstweekday=0)
        month_weeks = c.monthdatescalendar(month_date.year, month_date.month)

        activities = Activity.objects.filter(
            topic__lesson_plan__subject__in=subjects).select_related('topic__lesson_plan__subject')
        assignments = Assignment.objects.filter(
            topic__lesson_plan__subject__in=subjects).select_related('topic__lesson_plan__subject')
        quizzes = Quiz.objects.filter(
            topic__lesson_plan__subject__in=subjects).select_related('topic__lesson_plan__subject')
        exams = Exam.objects.filter(subject__in=subjects).select_related('subject')
        projects = Project.objects.filter(
            subject__in=subjects, deadline__isnull=False).select_related('subject')
        personal_tasks = PersonalTask.objects.filter(
            student=user, no_deadline=False) if is_personal_student else PersonalTask.objects.none()

        weeks_data = []
        for week in month_weeks:
            week_start, week_end = week[0], week[-1]
            bars = []
            row = 1

            for activity in activities:
                a_start, a_end = activity.created_at.date(), activity.deadline
                if a_end < week_start or a_start > week_end:
                    continue
                ib_start, ib_end = max(a_start, week_start), min(a_end, week_end)
                bars.append({
                    'label': f"{activity.topic.lesson_plan.subject.name}: {activity.title}",
                    'css_class': 'cal-item-bar cal-activity-bar',
                    'col_start': (ib_start - week_start).days + 1,
                    'col_span': (ib_end - ib_start).days + 1,
                    'row': row, 'url_name': 'activity_detail', 'obj_id': activity.id,
                })
                row += 1

            for assignment in assignments:
                a_start, a_end = assignment.created_at.date(), assignment.deadline
                if a_end < week_start or a_start > week_end:
                    continue
                ib_start, ib_end = max(a_start, week_start), min(a_end, week_end)
                bars.append({
                    'label': f"{assignment.topic.lesson_plan.subject.name}: {assignment.title}",
                    'css_class': 'cal-item-bar cal-assignment-bar',
                    'col_start': (ib_start - week_start).days + 1,
                    'col_span': (ib_end - ib_start).days + 1,
                    'row': row, 'url_name': 'assignment_detail', 'obj_id': assignment.id,
                })
                row += 1

            for quiz in quizzes:
                q_start, q_end = quiz.created_at.date(), quiz.deadline
                if q_end < week_start or q_start > week_end:
                    continue
                ib_start, ib_end = max(q_start, week_start), min(q_end, week_end)
                bars.append({
                    'label': f"{quiz.topic.lesson_plan.subject.name}: {quiz.title}",
                    'css_class': 'cal-item-bar cal-quiz-bar',
                    'col_start': (ib_start - week_start).days + 1,
                    'col_span': (ib_end - ib_start).days + 1,
                    'row': row, 'url_name': 'quiz_detail', 'obj_id': quiz.id,
                })
                row += 1

            for exam in exams:
                if exam.deadline < week_start or exam.deadline > week_end:
                    continue
                bars.append({
                    'label': f"{exam.subject.name}: {exam.get_exam_type_display()}",
                    'css_class': 'cal-item-bar cal-exam-bar',
                    'col_start': (exam.deadline - week_start).days + 1,
                    'col_span': 1,
                    'row': row, 'url_name': 'exam_detail', 'obj_id': exam.id,
                })
                row += 1

            for project in projects:
                p_start, p_end = project.created_at.date(), project.deadline
                if p_end < week_start or p_start > week_end:
                    continue
                ib_start, ib_end = max(p_start, week_start), min(p_end, week_end)
                bars.append({
                    'label': f"{project.subject.name}: {project.title}",
                    'css_class': 'cal-item-bar cal-project-bar',
                    'col_start': (ib_start - week_start).days + 1,
                    'col_span': (ib_end - ib_start).days + 1,
                    'row': row, 'url_name': 'project_detail', 'obj_id': project.id,
                })
                row += 1

            for task in personal_tasks:
                if task.deadline < week_start or task.deadline > week_end:
                    continue
                bars.append({
                    'label': task.title,
                    'css_class': 'cal-item-bar cal-task-bar' + (' cal-bar-done' if task.completed else ''),
                    'col_start': (task.deadline - week_start).days + 1,
                    'col_span': 1,
                    'row': row, 'url_name': 'personal_task_detail', 'obj_id': task.id,
                })
                row += 1

            weeks_data.append({'days': week, 'bars': bars, 'row_count': row})

        prev_month = (month_date - timedelta(days=1)).replace(day=1)
        next_month = (month_date.replace(day=28) +
                       timedelta(days=4)).replace(day=1)

        context.update({
            'weeks_data': weeks_data, 'month_name': month_date.strftime('%B %Y'),
            'prev_month': prev_month.strftime('%Y-%m'),
            'next_month': next_month.strftime('%Y-%m'),
            'this_month': today.strftime('%Y-%m'),
        })

    return render(request, 'tracker/tasks_calendar.html', context)


@login_required
def calendar_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    today = timezone.now().date()
    c = cal_module.Calendar(firstweekday=0)
    month_weeks = c.monthdatescalendar(today.year, today.month)

    topics = subject.lesson_plan.topics.all()
    projects = subject.projects.filter(deadline__isnull=False)
    exams = subject.exams.all()

    weeks_data = []
    for week in month_weeks:
        week_start, week_end = week[0], week[-1]
        bars = []
        row = 1

        visible_topics = []
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
            visible_topics.append(topic)

        for exam in exams:
            if exam.deadline < week_start or exam.deadline > week_end:
                continue
            bars.append({
                'label': f"{exam.get_exam_type_display()}",
                'css_class': 'cal-item-bar cal-exam-bar',
                'col_start': (exam.deadline - week_start).days + 1,
                'col_span': 1,
                'row': row,
                'url_name': 'exam_detail', 'obj_id': exam.id,
            })
            row += 1

        for topic in visible_topics:
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

            for quiz in topic.quizzes.all():
                q_start, q_end = quiz.created_at.date(), quiz.deadline
                if q_end < week_start or q_start > week_end:
                    continue
                ib_start = max(q_start, week_start)
                ib_end = min(q_end, week_end)
                bars.append({
                    'label': f"{quiz.title}",
                    'css_class': 'cal-item-bar cal-quiz-bar',
                    'col_start': (ib_start - week_start).days + 1,
                    'col_span': (ib_end - ib_start).days + 1,
                    'row': row,
                    'url_name': 'quiz_detail', 'obj_id': quiz.id,
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
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(
        Assignment, id=assignment_id, topic__lesson_plan__subject__teacher=request.user)
    subject_id = assignment.topic.lesson_plan.subject.id
    if request.method == 'POST':
        assignment.delete()
        return redirect('lesson_plan_view', subject_id=subject_id)
    return render(request, 'tracker/confirm_delete.html', {'object_name': assignment.title, 'cancel_url': 'lesson_plan_view', 'cancel_arg': subject_id})


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

#exams

EXAM_TYPE_LABELS = dict(Exam.EXAM_TYPE_CHOICES)

@login_required
def exam_router(request, subject_id, exam_type):
    subject = get_object_or_404(Subject, id=subject_id)
    is_manager = subject.teacher == request.user
    exam = Exam.objects.filter(subject=subject, exam_type=exam_type).first()

    if exam:
        return redirect('exam_detail', exam_id=exam.id)
    if is_manager:
        return redirect('add_exam', subject_id=subject.id, exam_type=exam_type)
    return render(request, 'tracker/exam_not_available.html', {
        'subject': subject, 'exam_type_label': EXAM_TYPE_LABELS.get(exam_type, exam_type),
    })


@login_required
def add_exam(request, subject_id, exam_type):
    subject = get_object_or_404(Subject, id=subject_id)
    if subject.teacher != request.user:
        return redirect('lesson_plan_view', subject_id=subject.id)
    if exam_type not in EXAM_TYPE_LABELS:
        return redirect('lesson_plan_view', subject_id=subject.id)

    existing = Exam.objects.filter(subject=subject, exam_type=exam_type).first()
    if existing:
        return redirect('exam_detail', exam_id=existing.id)

    if request.method == 'POST':
        form = ExamForm(request.POST, request.FILES)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.subject = subject
            exam.exam_type = exam_type
            exam.save()
            return redirect('add_exam_skill', exam_id=exam.id)
    else:
        form = ExamForm()
    return render(request, 'tracker/add_exam.html', {
        'form': form, 'subject': subject, 'exam_type_label': EXAM_TYPE_LABELS.get(exam_type, exam_type),
    })


@login_required
def add_exam_skill_weight(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    subject = exam.subject
    if subject.teacher != request.user:
        return redirect('exam_detail', exam_id=exam.id)

    relevant_skills = get_relevant_skills()
    if request.method == 'POST':
        form = ExamSkillWeightForm(request.POST, exam=exam, relevant_skills=relevant_skills)
        if form.is_valid():
            weight = form.save(commit=False)
            weight.exam = exam
            weight.save()
            return redirect('add_exam_skill', exam_id=exam.id)
    else:
        form = ExamSkillWeightForm(exam=exam, relevant_skills=relevant_skills)

    total_percentage = exam.skill_weights.aggregate(total=Sum('percentage'))['total'] or 0
    return render(request, 'tracker/add_exam_skill.html', {
        'exam': exam, 'form': form, 'skills': relevant_skills, 'total_percentage': total_percentage,
    })


@login_required
def exam_detail(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    subject = exam.subject
    is_owner = subject.teacher == request.user
    is_personal = request.user.profile.mode == 'personal'

    if is_owner and is_personal:
        completion = ExamCompletion.objects.filter(exam=exam, student=request.user).first()
        if request.method == 'POST' and not completion:
            completion = ExamCompletion.objects.create(exam=exam, student=request.user)
            return redirect('grade_exam_completion', completion_id=completion.id)
        return render(request, 'tracker/exam_detail_personal.html', {'exam': exam, 'completion': completion})

    if is_owner:
        completions = exam.completions.select_related('student').all()
        pending_count = completions.filter(graded=False).count()
        return render(request, 'tracker/exam_detail_teacher.html', {
            'exam': exam, 'completions': completions, 'pending_count': pending_count,
        })

    completion = ExamCompletion.objects.filter(exam=exam, student=request.user).first()
    if request.method == 'POST' and not completion:
        completion = ExamCompletion.objects.create(exam=exam, student=request.user)
    return render(request, 'tracker/exam_detail.html', {'exam': exam, 'completion': completion})


@login_required
def grade_exam_completion(request, completion_id):
    completion = get_object_or_404(ExamCompletion, id=completion_id)
    exam = completion.exam
    if exam.subject.teacher != request.user:
        return redirect('home')

    if request.method == 'POST' and not completion.graded:
        form = GradeExamForm(request.POST, instance=completion, max_score=exam.max_score)
        if form.is_valid():
            completion = form.save(commit=False)
            completion.graded = True
            completion.save()
            total_points = completion.total_points
            for weight in exam.skill_weights.all():
                delta = total_points * weight.percentage // 100
                student_skill, created = completion.student.skills.get_or_create(skill=weight.skill)
                points_before = student_skill.points
                points_after = max(0, points_before + delta)
                student_skill.points = points_after
                student_skill.save()
                ExamSkillAward.objects.create(
                    completion=completion, skill=weight.skill, delta=delta,
                    points_before=points_before, points_after=points_after,
                )
            return redirect('grade_exam_completion', completion_id=completion.id)
    else:
        form = GradeExamForm(instance=completion, max_score=exam.max_score)

    return render(request, 'tracker/grade_exam_completion.html', {
        'exam': exam, 'completion': completion, 'form': form,
        'pool': exam.max_score // 2,
        'total_points': completion.total_points if completion.graded else None,
    })

@login_required
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, subject__teacher=request.user)
    subject_id = exam.subject.id
    if request.method == 'POST':
        exam.delete()
        return redirect('lesson_plan_view', subject_id=subject_id)
    return render(request, 'tracker/confirm_delete.html', {
        'object_name': exam.get_exam_type_display(), 'cancel_url': 'lesson_plan_view', 'cancel_arg': subject_id,
    })