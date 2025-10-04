from django.db import migrations, models
from django.utils import timezone

def backfill_timestamps(apps, schema_editor):
    OrderProduct = apps.get_model('orders', 'OrderProduct')
    now = timezone.now()
    # Backfill rows created before these columns existed
    OrderProduct.objects.filter(created_at__isnull=True).update(
        created_at=now,
        updated_at=now,
    )

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_add_orderproduct_timestamps'),
    ]

    operations = [
        # Add as NULLable first so existing rows don't block the migration
        migrations.AddField(
            model_name='orderproduct',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='orderproduct',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),

        # Backfill existing rows
        migrations.RunPython(backfill_timestamps, migrations.RunPython.noop),

        # Then enforce non-null (to match your model)
        migrations.AlterField(
            model_name='orderproduct',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='orderproduct',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
