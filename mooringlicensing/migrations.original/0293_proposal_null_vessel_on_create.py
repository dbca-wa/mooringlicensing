# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-05-12 07:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0292_applicationfee_system_invoice'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='null_vessel_on_create',
            field=models.BooleanField(default=True),
        ),
    ]
