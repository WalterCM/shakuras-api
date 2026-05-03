from django.views.generic import DetailView, TemplateView
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from django.core.files.uploadedfile import UploadedFile
import json
import yaml
from rest_framework import viewsets, permissions
from matches.models import Match
from matches import serializers
from matches.scenario import list_scenarios, run_scenario_from_file, SCENARIOS_DIR
from matches.loader import load_map, get_maps_list, UNIT_DEFINITIONS


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unit_definitions'] = UNIT_DEFINITIONS
        return context


class MapEditorView(TemplateView):
    """Interactive map editor for designing layouts"""
    template_name = 'matches/map_editor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unit_definitions'] = UNIT_DEFINITIONS
        return context


def list_maps_api(request):
    """API endpoint to list all available maps for the editor"""
    from matches.loader import MAPS_DIR
    maps = []
    if MAPS_DIR.exists():
        for yaml_file in sorted(MAPS_DIR.glob('*.yaml')):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                maps.append({
                    'filename': yaml_file.stem,
                    'name': data.get('name', yaml_file.stem),
                    'width': data.get('width', 128),
                    'height': data.get('height', 128),
                })
            except Exception:
                pass
    return JsonResponse({'maps': maps})


def load_map_api(request):
    """API endpoint to load a map's full data for editing"""
    from matches.loader import MAPS_DIR
    filename = request.GET.get('name', '')
    map_path = MAPS_DIR / f"{filename}.yaml"
    if not map_path.exists():
        return JsonResponse({'status': 'error', 'message': 'Map not found'}, status=404)
    try:
        with open(map_path, 'r') as f:
            data = yaml.safe_load(f)
        return JsonResponse({'status': 'ok', 'map': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
def save_map_view(request):
    """API endpoint to save a map layout to YAML file"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            from matches.loader import MAPS_DIR
            
            map_filename = data.get('filename')
            if not map_filename:
                map_filename = data.get('name', 'New Map').replace(' ', '_').lower()
            
            map_path = MAPS_DIR / f"{map_filename}.yaml"
            
            # Build entities list from minerals
            entities = []
            for i, m in enumerate(data.get('minerals', [])):
                entities.append({
                    'id': f'm{i+1}',
                    'type': 'mineral_patch',
                    'owner': 'neutral',
                    'x': m['x'],
                    'y': m['y'],
                })
            
            yaml_content = {
                'name': data.get('name', 'New Map'),
                'description': data.get('description', ''),
                'width': data.get('width', 128),
                'height': data.get('height', 128),
                'spawn_points': data.get('spawn_points', {}),
                'entities': entities,
            }
            
            # Persist reference image filename if provided
            ref_image = data.get('reference_image')
            if ref_image:
                yaml_content['reference_image'] = ref_image
            
            with open(map_path, 'w') as f:
                yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)
            
            return JsonResponse({'status': 'ok', 'path': str(map_path)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)


@csrf_exempt
def upload_reference_api(request):
    """Upload a reference image to maps/references/"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST only'}, status=405)
    
    file = request.FILES.get('image')
    if not file:
        return JsonResponse({'status': 'error', 'message': 'No image provided'}, status=400)
    
    from matches.loader import MAPS_DIR
    ref_dir = MAPS_DIR / 'references'
    ref_dir.mkdir(exist_ok=True)
    
    # Sanitize filename
    import re
    safe_name = re.sub(r'[^\w.\-]', '_', file.name)
    dest = ref_dir / safe_name
    
    with open(dest, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)
    
    return JsonResponse({'status': 'ok', 'filename': safe_name})


def serve_reference_api(request):
    """Serve a reference image from maps/references/"""
    from django.http import FileResponse
    from matches.loader import MAPS_DIR
    
    filename = request.GET.get('name', '')
    if not filename:
        return JsonResponse({'status': 'error', 'message': 'No filename'}, status=400)
    
    filepath = MAPS_DIR / 'references' / filename
    if not filepath.exists() or not filepath.is_file():
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    
    return FileResponse(open(filepath, 'rb'))


class ScenarioVisualizerView(TemplateView):
    """Visualizer for scenarios (without database)"""
    template_name = 'matches/scenario_visualizer.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['scenarios'] = list_scenarios()
        context['unit_definitions'] = UNIT_DEFINITIONS
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
            
            # Execute scenario directly (scenarios now include all needed data)
            from matches.scenario import execute_scenario
            replay_data = execute_scenario(scenario_data)
            
            return JsonResponse({'status': 'ok', 'replay': replay_data})
        except yaml.YAMLError as e:
            return JsonResponse({'status': 'error', 'message': f'YAML error: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
