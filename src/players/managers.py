import random
from django.db import models
from faker import Faker
from hangul_names.transliterator import Transliterator

class PlayerManager(models.Manager):
    def generate_player(self, nickname=None):
        from .models import Player
        from shakuras.utils import CustomWordProvider
        
        locales = [
            ('Korea', 'ko_KR', 5),
            ('United States', 'en_US', 3),
            ('Spain', 'es_ES', 2),
        ]
        weighted_locales = [(country, locale) for country, locale, weight in locales for _ in range(weight)]
        country, locale = random.choices(weighted_locales)[0]
        fake = Faker(locale)
        fake.add_provider(CustomWordProvider)

        t = Transliterator()

        if locale == 'ko_KR':
            name = t.romanize(fake.name()).split(' ')
            first_name = name[1]
            last_name = name[0]
        else:
            first_name = fake.first_name()
            last_name = fake.last_name()

        nickname = nickname or fake.word_with_min_length(3).capitalize()

        # Weighted race selection (Random is extremely rare)
        race_choices = [Player.RACE.TERRAN, Player.RACE.ZERG, Player.RACE.PROTOSS, Player.RACE.RANDOM]
        race_weights = [33, 33, 33, 1]
        race = random.choices(race_choices, weights=race_weights)[0]

        payload = {
            'first_name': first_name,
            'last_name': last_name,
            'nickname': nickname,
            'country': country,
            'race': race,
            'macro': random.randint(10, 80),
            'micro': random.randint(10, 80),
            'multitasking': random.randint(10, 80),
            'strategy': random.randint(10, 80),
        }
        player = Player(**payload)

        return player
