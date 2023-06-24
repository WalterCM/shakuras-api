from rest_framework import generics
from rest_framework import permissions

from players import serializers
from core.models import Player


class ManagePlayerView(generics.ListAPIView):
    serializer_class = serializers.PlayerSerializer
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Player.objects.all()
