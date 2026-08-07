from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from avatar.models import Skill
from datetime import timedelta


class Subject(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='subjects_taught')
    students = models.ManyToManyField(
        User, related_name='subjects_enrolled', blank=True)
    activity_weight = models.PositiveIntegerField(default=50)
    project_weight = models.PositiveIntegerField(default=50)
    at_risk_threshold = models.PositiveIntegerField(default=75)

    def __str__(self):
        return self.name


class LessonPlan(models.Model):
    subject = models.OneToOneField(
        Subject, on_delete=models.CASCADE, related_name='lesson_plan')

    def __str__(self):
        return f"Lesson Plan for {self.subject.name}"


class Topic(models.Model):
    lesson_plan = models.ForeignKey(
        LessonPlan, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.title} ({self.start_date} – {self.end_date})"


class TopicDocument(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='topic_documents')
    document = models.FileField(upload_to='topic_materials/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']


class TopicImage(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='topic_images')
    image = models.ImageField(upload_to='topic_materials/images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']


class Activity(models.Model):
    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name='activities')
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    max_score = models.PositiveIntegerField(default=100)

    skill_main = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, related_name='activities_main')
    skill_secondary = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities_secondary')
    skill_tertiary = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities_tertiary')

    @property
    def due_soon(self):
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    def __str__(self):
        return self.title


class ActivityCompletion(models.Model):
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='completions')
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='activity_completions')
    image = models.ImageField(
        upload_to='activity_submissions/images/', null=True, blank=True)
    document = models.FileField(
        upload_to='activity_submissions/documents/', null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('activity', 'student')

    @property
    def total_points(self):
        if self.score is None or not self.activity.max_score:
            return 0
        pool = self.activity.max_score // 2
        return pool * self.score // self.activity.max_score

    @property
    def _skill_weights(self):
        weights = [5]
        weights.append(3 if self.activity.skill_secondary else 0)
        weights.append(2 if self.activity.skill_tertiary else 0)
        return weights

    @property
    def main_points(self):
        weights = self._skill_weights
        return self.total_points * weights[0] // sum(weights)

    @property
    def secondary_points(self):
        if not self.activity.skill_secondary:
            return 0
        weights = self._skill_weights
        return self.total_points * weights[1] // sum(weights)

    @property
    def tertiary_points(self):
        if not self.activity.skill_tertiary:
            return 0
        weights = self._skill_weights
        return self.total_points * weights[2] // sum(weights)

    def __str__(self):
        return f"{self.student.username} completed {self.activity.title}"


class Project(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    max_score = models.PositiveIntegerField(default=100)

    def __str__(self):
        return self.title


class ProjectSubmission(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='project_submissions')
    image = models.ImageField(
        upload_to='project_submissions/images/', null=True, blank=True)
    document = models.FileField(
        upload_to='project_submissions/documents/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    evaluated = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'student')

    def __str__(self):
        return f"{self.student.username} - {self.project.title}"


class SkillAward(models.Model):
    submission = models.ForeignKey(
        ProjectSubmission, on_delete=models.CASCADE, related_name='skill_awards')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    points = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.skill.name}: {self.points} pts"


class PersonalTask(models.Model):
    DIFFICULTY_CHOICES = [(1, 'Easy'), (2, 'Medium'), (3, 'Hard')]
    IMPORTANCE_CHOICES = [(1, 'Low'), (2, 'Medium'), (3, 'High')]
    REPEAT_CHOICES = [
        ('none', 'Does not repeat'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]
    WEEKDAY_CHOICES = [
        ('mon', 'Mon'), ('tue', 'Tue'), ('wed', 'Wed'), ('thu', 'Thu'),
        ('fri', 'Fri'), ('sat', 'Sat'), ('sun', 'Sun'),
    ]

    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='personal_tasks')
    title = models.CharField(max_length=200)
    no_deadline = models.BooleanField(default=False)
    deadline = models.DateField(null=True, blank=True)
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES)
    importance = models.IntegerField(choices=IMPORTANCE_CHOICES)

    skill_main = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name='personal_tasks_main')
    skill_secondary = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='personal_tasks_secondary')
    skill_tertiary = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='personal_tasks_tertiary')

    repeat = models.CharField(
        max_length=10, choices=REPEAT_CHOICES, default='none')
    weekly_days = models.CharField(max_length=50, blank=True)
    notify = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)

    @property
    def due_soon(self):
        if self.no_deadline or not self.deadline:
            return False
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    @property
    def points_value(self):
        return self.difficulty * self.importance * 10

    @property
    def main_points(self):
        return self.points_value * 5 // 10

    @property
    def secondary_points(self):
        return self.points_value * 3 // 10

    @property
    def tertiary_points(self):
        return self.points_value * 2 // 10

    def get_weekly_days_display(self):
        if not self.weekly_days:
            return ''
        day_dict = dict(self.WEEKDAY_CHOICES)
        return ', '.join(day_dict.get(d, d) for d in self.weekly_days.split(','))

    def __str__(self):
        return self.title

class Quiz(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    deadline = models.DateField()
    max_score = models.PositiveIntegerField(default=100)
    passing_percentage = models.PositiveIntegerField(default=60)
    file = models.FileField(upload_to='quiz_materials/', null=True, blank=True)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def passing_score(self):
        return round(self.max_score * self.passing_percentage / 100)

    @property
    def due_soon(self):
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    def __str__(self):
        return self.title


class QuizSkillWeight(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='skill_weights')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    percentage = models.PositiveIntegerField()

    class Meta:
        unique_together = ('quiz', 'skill')

    def __str__(self):
        return f"{self.skill.name}: {self.percentage}%"


class QuizCompletion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='completions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_completions')
    marked_done_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('quiz', 'student')

    @property
    def total_points(self):
        if self.score is None:
            return 0
        quiz = self.quiz
        pool = quiz.max_score // 2
        threshold = quiz.passing_score
        if self.score >= threshold:
            span = quiz.max_score - threshold
            if span <= 0:
                return pool
            return int(pool * (self.score - threshold) / span)
        else:
            if threshold <= 0:
                return 0
            return -int(pool * (threshold - self.score) / threshold)

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"
    
class QuizSkillAward(models.Model):
    completion = models.ForeignKey(QuizCompletion, on_delete=models.CASCADE, related_name='skill_awards')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    delta = models.IntegerField()
    points_before = models.PositiveIntegerField()
    points_after = models.PositiveIntegerField()

    @property
    def level_before(self):
        return self.points_before // 100

    @property
    def level_after(self):
        return self.points_after // 100

    @property
    def points_into_level_before(self):
        return self.points_before % 100

    @property
    def points_into_level_after(self):
        return self.points_after % 100

    def __str__(self):
        return f"{self.skill.name}: {self.delta:+d}"

class Exam(models.Model):
    EXAM_TYPE_CHOICES = [
        ('prelim', 'Prelim Exam'),
        ('midterm', 'Midterm Exam'),
        ('prefinal', 'Prefinal Exam'),
        ('final', 'Final Exam'),
    ]
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exams')
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    instructions = models.TextField(blank=True)
    deadline = models.DateField()
    max_score = models.PositiveIntegerField(default=100)
    passing_percentage = models.PositiveIntegerField(default=60)
    file = models.FileField(upload_to='exam_materials/files/', null=True, blank=True)
    image = models.ImageField(upload_to='exam_materials/images/', null=True, blank=True)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('subject', 'exam_type')

    @property
    def passing_score(self):
        return round(self.max_score * self.passing_percentage / 100)

    @property
    def due_soon(self):
        return 0 <= (self.deadline - timezone.now().date()).days <= 3

    def __str__(self):
        return f"{self.subject.name} - {self.get_exam_type_display()}"


class ExamSkillWeight(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='skill_weights')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    percentage = models.PositiveIntegerField()

    class Meta:
        unique_together = ('exam', 'skill')

    def __str__(self):
        return f"{self.skill.name}: {self.percentage}%"


class ExamCompletion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='completions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_completions')
    marked_done_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('exam', 'student')

    @property
    def total_points(self):
        if self.score is None:
            return 0
        exam = self.exam
        pool = exam.max_score // 2
        threshold = exam.passing_score
        if self.score >= threshold:
            span = exam.max_score - threshold
            if span <= 0:
                return pool
            return int(pool * (self.score - threshold) / span)
        else:
            if threshold <= 0:
                return 0
            return -int(pool * (threshold - self.score) / threshold)

    def __str__(self):
        return f"{self.student.username} - {self.exam}"


class ExamSkillAward(models.Model):
    completion = models.ForeignKey(ExamCompletion, on_delete=models.CASCADE, related_name='skill_awards')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    delta = models.IntegerField()
    points_before = models.PositiveIntegerField()
    points_after = models.PositiveIntegerField()

    @property
    def level_before(self):
        return self.points_before // 100

    @property
    def level_after(self):
        return self.points_after // 100

    @property
    def points_into_level_before(self):
        return self.points_before % 100

    @property
    def points_into_level_after(self):
        return self.points_after % 100

    def __str__(self):
        return f"{self.skill.name}: {self.delta:+d}"