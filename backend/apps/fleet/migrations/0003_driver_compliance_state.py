# Generated manually for Sentinel continuous compliance fields

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0002_driver_hos_violations_90d_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="driver",
            name="compliance_state",
            field=models.CharField(
                choices=[
                    ("clear", "Clear"),
                    ("watch", "Watch"),
                    ("restricted", "Restricted"),
                    ("suspended", "Suspended"),
                ],
                db_index=True,
                default="clear",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="driver",
            name="compliance_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="driver",
            name="compliance_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="driver",
            name="compliance_history",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
