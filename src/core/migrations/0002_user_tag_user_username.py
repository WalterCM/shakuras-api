# Generated by Django 4.1.4 on 2023-06-24 00:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='tag',
            field=models.CharField(default='tag', max_length=30, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='user',
            name='username',
            field=models.CharField(default='username', max_length=30),
            preserve_default=False,
        ),
    ]
