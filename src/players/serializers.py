
from rest_framework import serializers

from core.models import Player


class PlayerSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Player"""
    team = serializers.CharField(source='team.name')

    class Meta:
        model = Player
        fields = (
            'first_name', 'last_name', 'nickname', 'country', 'team'
        )
