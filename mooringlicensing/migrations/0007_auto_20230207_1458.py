# Generated by Django 3.2.16 on 2023-02-07 06:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0006_auto_20230207_1456'),
    ]

    operations = [
        migrations.AddField(
            model_name='dcvadmissionfee',
            name='uuid',
            field=models.CharField(blank=True, max_length=36, null=True),
        ),
        migrations.AddField(
            model_name='dcvpermitfee',
            name='uuid',
            field=models.CharField(blank=True, max_length=36, null=True),
        ),
    ]
