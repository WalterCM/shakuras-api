# Generated by Django 4.1.9 on 2023-07-01 18:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_match_tournament_matchparticipant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='nickname',
            field=models.CharField(max_length=20),
        ),
    ]