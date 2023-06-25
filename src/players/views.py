from rest_framework import mixins, status, viewsets, permissions

from players import serializers
from core.models import Player


class PlayerViewSet(mixins.RetrieveModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.PlayerSerializer
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Player.objects.all()
    lookup_field = 'nickname'
