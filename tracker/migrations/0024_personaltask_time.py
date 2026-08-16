from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0023_subject_split_activity_quiz_weights'),
    ]

    operations = [
        migrations.AddField(
            model_name='personaltask',
            name='time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]