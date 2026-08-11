from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0019_exam_examcompletion_examskillaward_examskillweight'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='quiz_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='prelim_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='midterm_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='prefinal_weight',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subject',
            name='final_weight',
            field=models.PositiveIntegerField(default=0),
        ),
    ]