"""
Map/Scenario loader.
Carga mapas desde archivos YAML en maps/ o scenarios/.
"""
import yaml
from pathlib import Path


MAPS_DIR = Path(__file__).parent.parent.parent / 'maps'
SCENARIOS_DIR = Path(__file__).parent.parent.parent / 'scenarios'


class MapLoadError(Exception):
    """Error loading a map or scenario."""
    pass


def load_map(name_or_path):
    """
    Carga un map desde archivo YAML.
    
    Args:
        name_or_path: Nombre del mapa (busca en maps/), ruta relativa (maps/ o scenarios/), 
                      o ruta absoluta/directa a archivo .yaml
    
    Returns:
        dict con la configuración del mapa
    
    Raises:
        MapLoadError: Si el mapa no se encuentra o no es válido
    """
    path = Path(name_or_path)
    
    # Caso 1: Es una ruta directa a un archivo .yaml
    if path.suffix == '.yaml':
        if path.exists():
            return _load_yaml(path)
        # Si es relativo, probar como ruta desde el proyecto
        project_path = Path(__file__).parent.parent.parent / path
        if project_path.exists():
            return _load_yaml(project_path)
        raise MapLoadError(f"File not found: {path}")
    
    # Caso 2: Solo nombre (buscar en maps/)
    maps_path = MAPS_DIR / f"{path}.yaml"
    if maps_path.exists():
        return _load_yaml(maps_path)
    
    # Caso 3: Buscar en scenarios/
    scenarios_path = SCENARIOS_DIR / path / f"{path}.yaml"
    if scenarios_path.exists():
        return _load_yaml(scenarios_path)
    
    # También probar sin subcarpeta
    scenarios_path_simple = SCENARIOS_DIR / f"{path}.yaml"
    if scenarios_path_simple.exists():
        return _load_yaml(scenarios_path_simple)
    
    raise MapLoadError(f"Map not found: {name_or_path}")


def _load_yaml(path):
    """Carga un archivo YAML y valida su contenido."""
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise MapLoadError(f"Invalid YAML in {path}: {e}")
    
    if not isinstance(data, dict):
        raise MapLoadError(f"Invalid map format in {path}: expected dict")
    
    # Validar campos requeridos
    _validate_map_data(data, path)
    
    return data


def _validate_map_data(data, path=None):
    """Valida que el mapa tenga los campos requeridos."""
    path_str = f" in {path}" if path else ""
    
    # Width y height son requeridos
    if 'width' not in data:
        raise MapLoadError(f"Missing 'width' field{path_str}")
    if 'height' not in data:
        raise MapLoadError(f"Missing 'height' field{path_str}")
    
    # Debe tener spawn_points O triggers (o ambos)
    has_spawns = 'spawn_points' in data and data['spawn_points']
    has_triggers = 'triggers' in data and data['triggers']
    has_entities = 'entities' in data and data['entities']
    
    if not has_spawns and not has_triggers:
        raise MapLoadError(
            f"Map must have 'spawn_points' or 'triggers'{path_str}. "
            f"Found: spawn_points={has_spawns}, triggers={has_triggers}"
        )
    
    return True


def get_maps_list():
    """Retorna lista de todos los mapas disponibles."""
    maps = []
    
    # Maps en maps/
    if MAPS_DIR.exists():
        for yaml_file in MAPS_DIR.glob('*.yaml'):
            data = _load_yaml(yaml_file)
            maps.append({
                'name': data.get('name', yaml_file.stem),
                'path': f'maps/{yaml_file.name}',
                'category': 'map',
                'width': data.get('width'),
                'height': data.get('height'),
            })
    
    # Maps en scenarios/
    if SCENARIOS_DIR.exists():
        for yaml_file in SCENARIOS_DIR.glob('**/*.yaml'):
            data = _load_yaml(yaml_file)
            rel_path = yaml_file.relative_to(SCENARIOS_DIR.parent)
            maps.append({
                'name': data.get('name', yaml_file.stem),
                'path': str(rel_path),
                'category': 'scenario',
                'width': data.get('width'),
                'height': data.get('height'),
            })
    
    return maps
