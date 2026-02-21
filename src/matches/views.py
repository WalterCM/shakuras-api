from django.views.generic import DetailView, TemplateView
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from django.core.files.uploadedfile import UploadedFile
import json
import yaml
from rest_framework import viewsets, permissions
from matches.models import Match, Map
from matches import serializers
from matches.scenario import list_scenarios, run_scenario_from_file, SCENARIOS_DIR


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


class ScenarioVisualizerView(TemplateView):
    """Visualizer for scenarios (without database)"""
    template_name = 'matches/scenario_visualizer.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['scenarios'] = list_scenarios()
        return context


def list_scenarios_api(request):
    """API endpoint to list all available scenarios"""
    return JsonResponse({'scenarios': list_scenarios()})


@csrf_exempt
def run_scenario_api(request):
    """API endpoint to run a scenario and return the replay data"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            scenario_path = data.get('path', '')
            
            # Validate path to prevent directory traversal
            full_path = (SCENARIOS_DIR / scenario_path).resolve()
            if not str(full_path).startswith(str(SCENARIOS_DIR.resolve())):
                return JsonResponse({'status': 'error', 'message': 'Invalid path'}, status=400)
            
            if not full_path.exists():
                return JsonResponse({'status': 'error', 'message': 'Scenario not found'}, status=404)
            
            replay_data = run_scenario_from_file(full_path)
            return JsonResponse({'status': 'ok', 'replay': replay_data})
        except yaml.YAMLError as e:
            return JsonResponse({'status': 'error', 'message': f'YAML error: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)


@csrf_exempt
def run_scenario_upload_api(request):
    """API endpoint to run a scenario from uploaded YAML file"""
    if request.method == 'POST':
        try:
            yaml_file = request.FILES.get('file')
            if not yaml_file:
                return JsonResponse({'status': 'error', 'message': 'No file provided'}, status=400)
            
            # Load YAML from uploaded file
            scenario_data = yaml.safe_load(yaml_file)
            
            # Get base map from DB if specified
            map_data = None
            if 'base_map' in scenario_data:
                try:
                    map_model = Map.objects.get(name__iexact=scenario_data['base_map'])
                    map_data = {
                        'name': map_model.name,
                        'width': map_model.width,
                        'height': map_model.height,
                        'spawn_points': map_model.spawn_points,
                        'minerals': map_model.minerals,
                    }
                except Map.DoesNotExist:
                    pass
            
            # Execute scenario
            from matches.scenario import execute_scenario
            replay_data = execute_scenario(scenario_data, map_data)
            
            return JsonResponse({'status': 'ok', 'replay': replay_data})
        except yaml.YAMLError as e:
            return JsonResponse({'status': 'error', 'message': f'YAML error: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
