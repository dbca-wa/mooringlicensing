# Generated by Django 3.2.16 on 2023-02-10 02:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mooringlicensing', '0008_stickeractionfee_uuid'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailUserLogEntry',
            fields=[
                ('communicationslogentry_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='mooringlicensing.communicationslogentry')),
                ('email_user_id', models.IntegerField(blank=True, null=True)),
            ],
            bases=('mooringlicensing.communicationslogentry',),
        ),
    ]
