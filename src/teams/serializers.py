
from rest_framework import serializers

from core.models import Team


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for team model"""

    class Meta:
        model = Team
        fields = ('name',)
