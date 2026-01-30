from django.views.generic import DetailView, TemplateView
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework import viewsets, permissions
from matches.models import Match, Map
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


class MapEditorView(TemplateView):
    """Interactive map editor for designing layouts"""
    template_name = 'matches/map_editor.html'


@csrf_exempt
def save_map_view(request):
    """API endpoint to save a new map layout"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_map = Map.objects.create(
                name=data.get('name', 'New Map'),
                width=data.get('width', 128),
                height=data.get('height', 128),
                spawn_points=data.get('spawn_points', {}),
                minerals=data.get('minerals', [])
            )
            return JsonResponse({'status': 'ok', 'id': new_map.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
