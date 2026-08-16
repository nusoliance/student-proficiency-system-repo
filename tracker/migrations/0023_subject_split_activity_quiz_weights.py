from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0022_activity_term_quiz_term_subject_divide_by_semester'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='final_activity_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='final_quiz_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='midterm_activity_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='midterm_quiz_weight',
            field=models.PositiveIntegerField(default=0),
        ),
    ]