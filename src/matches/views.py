from django.views.generic import DetailView
from rest_framework import viewsets, permissions
from matches.models import Match
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


class ReplayView(DetailView):
    """Standard Django view to visualize a match replay"""
    model = Match
    template_name = 'matches/replay_visualizer.html'
    context_object_name = 'match'
