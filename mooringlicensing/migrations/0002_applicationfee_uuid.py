# Generated by Django 3.2.16 on 2023-01-11 06:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationfee',
            name='uuid',
            field=models.CharField(blank=True, max_length=36, null=True),
        ),
    ]
