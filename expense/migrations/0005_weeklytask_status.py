from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expense', '0004_weeklytask_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='weeklytask',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')],
                default='pending', max_length=10,
            ),
        ),
    ]
