# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-05-21 08:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0120_merge_20210521_0925'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mooring',
            name='mooring_bookings_mooring_specification',
            field=models.IntegerField(choices=[(1, 'Rental Mooring'), (2, 'Private Mooring')]),
        ),
    ]