# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-23 06:58
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0101_auto_20210423_1436'),
    ]

    operations = [
        migrations.AddField(
            model_name='dcvadmissionfee',
            name='fee_constructor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='dcv_admission_fees', to='mooringlicensing.FeeConstructor'),
        ),
    ]
