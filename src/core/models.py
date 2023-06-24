from django.db import models

from users.models import AbstractUser


class User(AbstractUser):
    username = models.CharField(max_length=30)
    tag = models.CharField(max_length=30, unique=True)


class Player(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    nickname = models.CharField(max_length=20)
    country = models.CharField(max_length=30)
    team = models.ForeignKey('Team', related_name='players', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return '{first_name} "{nickname}" {last_name}'.format(
            first_name=self.first_name,
            nickname=self.nickname,
            last_name=self.last_name
        )


class Team(models.Model):
    name = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
