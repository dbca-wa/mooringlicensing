# Generated by Django 3.2.18 on 2023-03-10 07:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0297_mooringbay_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proposal',
            name='vessel_type',
            field=models.CharField(blank=True, choices=[('catamaran', 'Catamaran'), ('bow_rider', 'Bow Rider'), ('cabin_ruiser', 'Cabin Cruiser'), ('centre_console', 'Centre Console'), ('ferry', 'Ferry'), ('rigid_inflatable', 'Rigid Inflatable'), ('half_cabin', 'Half Cabin'), ('inflatable', 'Inflatable'), ('launch', 'Launch'), ('motor_sailer', 'Motor Sailer'), ('multihull', 'Multihull'), ('open_boat', 'Open Boat'), ('power_boat', 'Power Boat'), ('pwc', 'PWC'), ('Runabout', 'Runabout'), ('fishing_boat', 'Fishing Boat'), ('tender', 'Tender'), ('walkaround', 'Walkaround'), ('other', 'Other')], max_length=20),
        ),
        migrations.AlterField(
            model_name='vesseldetails',
            name='vessel_draft',
            field=models.DecimalField(decimal_places=2, max_digits=8),
        ),
        migrations.AlterField(
            model_name='vesseldetails',
            name='vessel_type',
            field=models.CharField(choices=[('catamaran', 'Catamaran'), ('bow_rider', 'Bow Rider'), ('cabin_ruiser', 'Cabin Cruiser'), ('centre_console', 'Centre Console'), ('ferry', 'Ferry'), ('rigid_inflatable', 'Rigid Inflatable'), ('half_cabin', 'Half Cabin'), ('inflatable', 'Inflatable'), ('launch', 'Launch'), ('motor_sailer', 'Motor Sailer'), ('multihull', 'Multihull'), ('open_boat', 'Open Boat'), ('power_boat', 'Power Boat'), ('pwc', 'PWC'), ('Runabout', 'Runabout'), ('fishing_boat', 'Fishing Boat'), ('tender', 'Tender'), ('walkaround', 'Walkaround'), ('other', 'Other')], max_length=20),
        ),
        migrations.AlterField(
            model_name='vesseldetails',
            name='vessel_weight',
            field=models.DecimalField(decimal_places=2, max_digits=8),
        ),
    ]
