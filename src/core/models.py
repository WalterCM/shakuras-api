from django.db import models

from users.models import AbstractUser
from users.models import UserManager as BaseUserManager


from faker import Faker


class UserManager(BaseUserManager):
    def get_test_payload(self):
        payload = super().get_test_payload()
        payload['nickname'] = 'Test'
        return payload

    def create_tag(self, nickname, email):
        """Tag creator. Not used"""
        minimum = 1001
        maximum = 9999
        word = nickname + email
        hashid = (hash(word) % (maximum - minimum)) + minimum
        tag = '{nickname}#{hashid}'.format(
            nickname=nickname, hashid=hashid
        )
        return tag

    def create_user(self, email=None, password=None, nickname=None, **extra_fields):
        """Manager that takes nickname into account"""
        if not nickname:
            raise ValueError('User requires a nickname')
        user = super().create_user(email, password, nickname=nickname, **extra_fields)

        return user


class User(AbstractUser):
    nickname = models.CharField(max_length=30, unique=True)

    objects = UserManager()

    @property
    def name(self):
        name = '{first_name} "{nickname}" {last_name}'
        return name.format(
            first_name=self.first_name,
            nickname=self.nickname,
            last_name=self.last_name
        )


class PlayerManager(models.Manager):
    def generate_player(self, nickname=None):
        import random
        from hangul_names.transliterator import Transliterator
        locales = [
            ('Korea', 'ko_KR', 5),
            ('United States', 'en_US', 3),
            ('Spain', 'es_ES', 2),
        ]
        weighted_locales = [(country, locale) for country, locale, weight in locales for _ in range(weight)]
        country, locale = random.choices(weighted_locales)[0]
        fake = Faker(locale)

        t = Transliterator()
        name = fake.name()

        if locale == 'ko_KR':
            name = t.romanize(name).split(' ')
            first_name = name[1]
            last_name = name[0]
        else:
            name = name.split(' ')
            first_name = name[0]
            last_name = name[1]

        payload = {
            'first_name': first_name,
            'last_name': last_name,
            'nickname': nickname or fake.word().capitalize(),
            'country': country
        }
        player = Player(**payload)

        return player


class Player(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    nickname = models.CharField(max_length=20, unique=True)
    country = models.CharField(max_length=30)
    team = models.ForeignKey('Team', related_name='players', on_delete=models.SET_NULL, null=True)

    objects = PlayerManager()

    def __str__(self):
        return self.name

    @property
    def name(self):
        name = '{first_name} "{nickname}" {last_name}'
        if self.country == 'Korea':
            name = '{last_name} "{nickname}" {first_name}'
        return name.format(
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
