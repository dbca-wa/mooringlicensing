# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2021-09-13 15:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0248_auto_20210912_1243'),
    ]

    operations = [
        migrations.AddField(
            model_name='dcvpermit',
            name='renewal_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='globalsettings',
            name='_file',
            field=models.FileField(blank=True, null=True, upload_to='approval_permit_template'),
        ),
        migrations.AlterField(
            model_name='globalsettings',
            name='key',
            field=models.CharField(choices=[('dcv_permit_template_file', 'DcvPermit template file'), ('dcv_admission_template_file', 'DcvAdmission template file'), ('approval_template_file', 'Approval template file'), ('minimum_vessel_length', 'Minimum vessel length'), ('minimum_mooring_vessel_length', 'Minimum mooring vessel length'), ('min_sticker_number_for_dcv_permit', 'Minimun sticker number for DCV Permit')], max_length=255),
        ),
    ]