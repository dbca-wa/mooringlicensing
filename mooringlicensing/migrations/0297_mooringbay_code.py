# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2023-01-24 05:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # ('mooringlicensing', '0296_auto_20220531_1555'),
        ('mooringlicensing', '0016_rename_proposal_applicant_details_proposal_personal_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='mooringbay',
            name='code',
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
    ]
