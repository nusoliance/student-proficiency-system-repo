from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0011_project_max_score_projectsubmission_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='activity_weight',
            field=models.PositiveIntegerField(default=50),
        ),
        migrations.AddField(
            model_name='subject',
            name='project_weight',
            field=models.PositiveIntegerField(default=50),
        ),
    ]