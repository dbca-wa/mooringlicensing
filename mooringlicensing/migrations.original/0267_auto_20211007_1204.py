# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-10-07 04:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0266_remove_applicationfee_fee_items'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='applicationfee',
            name='fee_items_for_aa',
        ),
        migrations.AddField(
            model_name='applicationfee',
            name='fee_items',
            field=models.ManyToManyField(related_name='application_fees', through='mooringlicensing.FeeItemApplicationFee', to='mooringlicensing.FeeItem'),
        ),
    ]