# Generated by Django 5.0.9 on 2024-10-22 02:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0365_delete_helppage_delete_previewtempapproval'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='approval',
            name='cover_letter_document',
        ),
        migrations.RemoveField(
            model_name='approval',
            name='extend_details',
        ),
        migrations.RemoveField(
            model_name='approval',
            name='extracted_fields',
        ),
        migrations.RemoveField(
            model_name='approval',
            name='proxy_applicant',
        ),
        migrations.RemoveField(
            model_name='approval',
            name='replaced_by',
        ),
        migrations.RemoveField(
            model_name='dcvpermit',
            name='renewal_sent',
        ),
        migrations.RemoveField(
            model_name='proposal',
            name='proxy_applicant',
        ),
    ]