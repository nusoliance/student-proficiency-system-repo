from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from tracker.models import Subject
from .models import ForumPost, Answer, Bookmark, Report
from .forms import ForumPostForm, AnswerForm, ReportForm
from avatar.models import Course


@login_required
def forum_list(request):
    if request.user.profile.role == 'teacher':
        subjects = Subject.objects.filter(teacher=request.user)
    else:
        subjects = request.user.subjects_enrolled.all()
    return render(request, 'forum/forum_list.html', {'subjects': subjects})


@login_required
def forum_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    posts = subject.posts.all().order_by('-created_at')
    if request.method == 'POST':
        form = ForumPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.subject = subject
            post.author = request.user
            post.save()
            return redirect('forum_view', subject_id=subject.id)
    else:
        form = ForumPostForm()
    bookmarked_ids = request.user.bookmark_set.values_list(
        'post_id', flat=True)
    return render(request, 'forum/forum_view.html', {
        'subject': subject, 'posts': posts, 'form': form, 'bookmarked_ids': bookmarked_ids
    })


@login_required
def post_detail(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)
    if request.method == 'POST':
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.post = post
            answer.author = request.user
            answer.save()
            return redirect('post_detail', post_id=post.id)
    else:
        form = AnswerForm()
    is_bookmarked = Bookmark.objects.filter(
        user=request.user, post=post).exists()
    return render(request, 'forum/post_detail.html', {
        'post': post, 'form': form, 'is_bookmarked': is_bookmarked
    })


@login_required
def toggle_bookmark(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)
    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user, post=post)
    if not created:
        bookmark.delete()
    return redirect('post_detail', post_id=post.id)


@login_required
def report_post(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id)
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.post = post
            report.user = request.user
            report.save()
            return redirect('post_detail', post_id=post.id)
    else:
        form = ReportForm()
    return render(request, 'forum/report_post.html', {'post': post, 'form': form})


@login_required
def course_forum_view(request, course_id=None):
    if course_id:
        course = get_object_or_404(Course, id=course_id)
    else:
        course = request.user.profile.course
        if not course:
            return render(request, 'forum/no_course_forum.html')

    posts = ForumPost.objects.filter(course=course).order_by('-created_at')
    if request.method == 'POST':
        form = ForumPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.course = course
            post.author = request.user
            post.save()
            return redirect('course_forum_view_detail', course_id=course.id) if course_id else redirect('course_forum_view')
    else:
        form = ForumPostForm()
    bookmarked_ids = request.user.bookmark_set.values_list(
        'post_id', flat=True)
    return render(request, 'forum/course_forum_view.html', {
        'course': course, 'posts': posts, 'form': form, 'bookmarked_ids': bookmarked_ids
    })


@login_required
def course_forum_list(request):
    courses = Course.objects.all()
    bookmarks = Bookmark.objects.filter(
        user=request.user).select_related('post', 'post__author')
    return render(request, 'forum/course_forum_list.html', {'courses': courses, 'bookmarks': bookmarks})


@login_required
def forum_list(request):
    if request.user.profile.role == 'teacher':
        subjects = Subject.objects.filter(teacher=request.user)
    elif request.user.profile.mode == 'professional':
        subjects = request.user.subjects_enrolled.all()
    else:
        subjects = Subject.objects.none()
    return render(request, 'forum/forum_list.html', {'subjects': subjects})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(ForumPost, id=post_id, author=request.user)
    if request.method == 'POST':
        if post.subject_id:
            redirect_target = redirect(
                'forum_view', subject_id=post.subject_id)
        else:
            redirect_target = redirect(
                'course_forum_view_detail', course_id=post.course_id)
        post.delete()
        return redirect_target
    preview = post.text[:60] if post.text else 'this post'
    return render(request, 'forum/confirm_delete.html', {'object_name': preview})


@login_required
def delete_answer(request, answer_id):
    answer = get_object_or_404(Answer, id=answer_id, author=request.user)
    post_id = answer.post_id
    if request.method == 'POST':
        answer.delete()
    return redirect('post_detail', post_id=post_id)
