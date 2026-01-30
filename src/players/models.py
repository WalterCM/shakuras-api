from django.db import models
from .managers import PlayerManager

class Player(models.Model):
    class RACE:
        TERRAN = 'terran'
        ZERG = 'zerg'
        PROTOSS = 'protoss'
        RANDOM = 'random'

        CHOICES = [
            (TERRAN, 'Terran'),
            (ZERG, 'Zerg'),
            (PROTOSS, 'Protoss'),
            (RANDOM, 'Random'),
        ]

    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    nickname = models.CharField(max_length=20)
    country = models.CharField(max_length=30)
    race = models.CharField(max_length=10, choices=RACE.CHOICES, default=RACE.RANDOM)
    team = models.ForeignKey('teams.Team', related_name='players', on_delete=models.SET_NULL, null=True)

    # Skills (0-100)
    macro = models.IntegerField(default=0)
    micro = models.IntegerField(default=0)
    multitasking = models.IntegerField(default=0)
    strategy = models.IntegerField(default=0)

    objects = PlayerManager()

    class Meta:
        db_table = 'core_player'

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
