# Generated by Django 5.0.8 on 2024-08-19 06:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0339_alter_proposalapplicant_first_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='mooringonapproval',
            name='active',
            field=models.BooleanField(default=True),
        ),
    ]
