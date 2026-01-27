from rest_framework import viewsets, permissions
from core.models import Match
from matches import serializers


class MatchViewSet(viewsets.ModelViewSet):
    """Viewset for managing matches"""
    serializer_class = serializers.MatchSerializer
    queryset = Match.objects.all()
    # For now, require authentication for any modification
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_queryset(self):
        """Retrieve matches for the current user (if applicable) or all"""
        return self.queryset.order_by('-date')
