from rest_framework import serializers
from core.models import Match, MatchParticipant, Player, Team
from players.serializers import PlayerSerializer
from teams.serializers import TeamSerializer


class MatchParticipantSerializer(serializers.ModelSerializer):
    """Serializer for match participant model"""
    participant = serializers.SerializerMethodField()

    class Meta:
        model = MatchParticipant
        fields = ('id', 'participant', 'score')
        read_only_fields = ('id',)

    def get_participant(self, obj):
        """Returns the serialized participant (Player or Team)"""
        if isinstance(obj.participant, Player):
            return PlayerSerializer(obj.participant).data
        elif isinstance(obj.participant, Team):
            return TeamSerializer(obj.participant).data
        return None


class MatchSerializer(serializers.ModelSerializer):
    """Serializer for match model"""
    participants = MatchParticipantSerializer(many=True, read_only=True)
    replay_log = serializers.JSONField(source='replay.log', read_only=True)

    class Meta:
        model = Match
        fields = ('id', 'date', 'status', 'participants', 'replay_log')
        read_only_fields = ('id',)
