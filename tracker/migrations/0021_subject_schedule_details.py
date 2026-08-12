import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0020_subject_quiz_and_exam_weights'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='delivery_mode',
            field=models.CharField(blank=True, choices=[('online', 'Online'), ('onsite', 'Onsite'), ('hybrid', 'Hybrid')], max_length=6),
        ),
        migrations.AddField(
            model_name='subject',
            name='end_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='professor_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='subject',
            name='room',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='subject',
            name='start_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='subject_type',
            field=models.CharField(blank=True, choices=[('lec', 'Lecture'), ('lab', 'Laboratory')], max_length=3),
        ),
        migrations.CreateModel(
            name='SubjectMeetingDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.CharField(choices=[('mon', 'Mon'), ('tue', 'Tue'), ('wed', 'Wed'), ('thu', 'Thu'), ('fri', 'Fri'), ('sat', 'Sat'), ('sun', 'Sun')], max_length=3)),
                ('mode', models.CharField(choices=[('online', 'Online'), ('onsite', 'Onsite')], max_length=6)),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meeting_days', to='tracker.subject')),
            ],
            options={
                'ordering': ['id'],
                'unique_together': {('subject', 'day')},
            },
        ),
    ]