# Generated by Django 3.2.20 on 2023-08-31 02:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0323_auto_20230829_1117'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companyownership',
            name='end_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
