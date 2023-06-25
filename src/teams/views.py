from rest_framework import generics
from rest_framework import permissions

from teams import serializers
from core.models import Team


class ManageTeamView(generics.ListAPIView):
    serializer_class = serializers.TeamSerializer
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Team.objects.all()
