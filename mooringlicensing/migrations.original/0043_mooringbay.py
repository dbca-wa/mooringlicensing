# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-06 06:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0042_proposal_insurance_choice'),
    ]

    operations = [
        migrations.CreateModel(
            name='MooringBay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name_plural': 'Mooring Bays',
            },
        ),
    ]