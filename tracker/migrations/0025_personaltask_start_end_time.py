from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0024_personaltask_time'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='personaltask',
            name='time',
        ),
        migrations.AddField(
            model_name='personaltask',
            name='end_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='personaltask',
            name='start_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]