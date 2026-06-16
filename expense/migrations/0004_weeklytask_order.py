from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expense', '0003_savingrecord_weeklytask'),
    ]

    operations = [
        migrations.AddField(
            model_name='weeklytask',
            name='order',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='weeklytask',
            options={'ordering': ['task_date', 'order', 'created_at']},
        ),
    ]
