# Generated by Django 4.1.4 on 2023-06-24 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_team_player_team'),
    ]

    operations = [
        migrations.RenameField(
            model_name='user',
            old_name='name',
            new_name='first_name',
        ),
        migrations.RenameField(
            model_name='user',
            old_name='username',
            new_name='nickname',
        ),
        migrations.AddField(
            model_name='user',
            name='last_name',
            field=models.CharField(default='Ross', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(error_messages={'unique': 'A user with that email address already exists.'}, max_length=254, unique=True, verbose_name='email address'),
        ),
        migrations.AlterField(
            model_name='user',
            name='tag',
            field=models.CharField(max_length=34, unique=True),
        ),
    ]
