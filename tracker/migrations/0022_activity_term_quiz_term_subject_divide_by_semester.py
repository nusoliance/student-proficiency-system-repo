from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0021_subject_schedule_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='term',
            field=models.CharField(blank=True, choices=[('midterm', 'Midterm'), ('final', 'Final')], default='midterm', max_length=7),
        ),
        migrations.AddField(
            model_name='quiz',
            name='term',
            field=models.CharField(blank=True, choices=[('midterm', 'Midterm'), ('final', 'Final')], default='midterm', max_length=7),
        ),
        migrations.AddField(
            model_name='subject',
            name='divide_by_semester',
            field=models.BooleanField(default=False),
        ),
    ]