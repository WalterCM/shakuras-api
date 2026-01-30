from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Map(models.Model):
    """Stores a map layout including dimensions, spawns, and minerals"""
    name = models.CharField(max_length=255)
    width = models.PositiveIntegerField(default=128)
    height = models.PositiveIntegerField(default=128)
    # List of {x, y, type: 'p1'|'p2'|'neutral'}
    spawn_points = models.JSONField(default=dict)
    # List of {x, y}
    minerals = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    date = models.DateTimeField()
    map = models.ForeignKey(Map, on_delete=models.SET_NULL, null=True, related_name='matches')

    class STATUS:
        IDLE = 'idle'
        ONGOING = 'ongoing'
        FINISHED = 'finished'

        CHOICES = [
            (IDLE, 'IDLE'),
            (ONGOING, 'ONGOING'),
            (FINISHED, 'FINISHED')
        ]

    status = models.CharField(
        choices=STATUS.CHOICES,
        max_length=10,
        default=STATUS.IDLE
    )

class MatchParticipant(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=(
                models.Q(app_label='players', model='Player') |
                models.Q(app_label='teams', model='Team')
        )
    )
    object_id = models.CharField(max_length=255)
    participant = GenericForeignKey('content_type', 'object_id')

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='participants')
    score = models.CharField(max_length=4)

class Tournament(models.Model):
    pass

class Replay(models.Model):
    """Stores the full log of a match simulation for playback"""
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='replay')
    log = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Replay for Match {self.match.id}"
