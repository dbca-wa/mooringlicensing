# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-03-09 03:52
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WaitingListApplication',
            fields=[
                ('proposal_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='mooringlicensing.Proposal')),
            ],
            bases=('mooringlicensing.proposal',),
        ),
    ]
