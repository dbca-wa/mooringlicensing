# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-03-15 23:58
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0278_sticker_replaced_for_renewal'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sticker',
            name='replaced_for_renewal',
        ),
    ]
