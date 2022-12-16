# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-04-23 03:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0097_auto_20210423_0931'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdmissionType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('landing', 'Landing'), ('extended_stay', 'Extended stay'), ('not_landing', 'Not landing'), ('approved_events', 'Approved events')], default='landing', max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name='AgeGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('adult', 'Adult'), ('child', 'Child')], default='adult', max_length=40)),
            ],
        ),
    ]