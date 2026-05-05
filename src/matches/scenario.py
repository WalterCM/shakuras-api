"""
Scenario loader and executor.
Loads YAML scenarios/maps and executes them using the MatchSimulator.
"""
import yaml
from pathlib import Path
from matches.engine import MatchSimulator, Entity, Map as EngineMap
from matches.actions import MoveAction, AttackAction, GatherAction, HoldAction
from matches.utils import Vector2D


SCENARIOS_DIR = Path(__file__).parent.parent.parent / 'scenarios'


def load_scenario_yaml(yaml_path):
    """Load a scenario from a YAML file."""
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)


def get_scenario_files():
    """Get list of all scenario files."""
    scenarios = []
    for category_dir in SCENARIOS_DIR.iterdir():
        if category_dir.is_dir():
            for yaml_file in category_dir.glob('*.yaml'):
                scenarios.append(yaml_file)
    return scenarios


def list_scenarios():
    """List all available scenarios with their paths."""
    scenarios = []
    for category_dir in SCENARIOS_DIR.iterdir():
        if category_dir.is_dir():
            category = category_dir.name
            for yaml_file in category_dir.glob('*.yaml'):
                data = load_scenario_yaml(yaml_file)
                scenarios.append({
                    'path': str(yaml_file.relative_to(SCENARIOS_DIR)),
                    'category': category,
                    'name': data.get('name', yaml_file.stem),
                    'description': data.get('description', ''),
                })
    return scenarios


def create_engine_map_from_config(map_config):
    """Create an Engine Map from map/scenario configuration dict."""
    spawn_points = {}
    for key, value in map_config.get('spawn_points', {}).items():
        if isinstance(value, dict):
            spawn_points[key] = Vector2D(value.get('x', 0), value.get('y', 0))
        else:
            spawn_points[key] = value
    
    return EngineMap(
        name=map_config.get('name', 'Scenario'),
        width=map_config.get('width', 128),
        height=map_config.get('height', 128),
        spawn_points=spawn_points,
        minerals=[],
        entities=map_config.get('entities', []),
    )


def create_action(action_config):
    """Create an Action object from action configuration."""
    action_type = action_config.get('type', '').lower()
    target = action_config.get('target', {})
    
    if action_type == 'move':
        return MoveAction(Vector2D(target.get('x', 0), target.get('y', 0)))
    elif action_type == 'attack':
        return AttackAction(target.get('id', target.get('entity', '')))
    elif action_type == 'gather':
        return GatherAction(target.get('id', target.get('entity', '')))
    elif action_type == 'hold':
        return HoldAction()
    
    return None


class DummyPlayer:
    """Minimal player object for scenarios that don't need real DB players."""
    def __init__(self, id):
        self.id = id
        self.nickname = id


def execute_scenario(scenario_data):
    """
    Execute a scenario and return the replay history.
    
    Configures a MatchSimulator with entities and triggers from the
    scenario YAML, then delegates to sim.simulate() for the actual loop.
    
    Args:
        scenario_data: Dict with scenario/map configuration
    
    Returns:
        List of tick deltas (replay history)
    """
    # 1. Create EngineMap from config
    engine_map = create_engine_map_from_config(scenario_data)
    
    # 2. Create simulator
    max_ticks = 300
    if scenario_data.get('config') and isinstance(scenario_data['config'], dict):
        max_ticks = scenario_data['config'].get('max_ticks', 300)
        
    sim = MatchSimulator(
        DummyPlayer('p1'),
        DummyPlayer('p2'),
        map_instance=engine_map,
        max_ticks=max_ticks
    )
    
    # 3. Disable AI controllers for scenarios
    sim.ai_controllers = []
    
    # 5. Create entities from YAML
    entities_config = scenario_data.get('entities', [])
    if not entities_config and scenario_data.get('spawn_points'):
        # Procedural setup for legacy/simple scenarios
        sim.setup_match()
    else:
        for entity_config in entities_config:
            if 'type' not in entity_config:
                continue
            
            entity = Entity(
                unit_type=entity_config['type'],
                owner_id=entity_config.get('owner', 'neutral'),
                x=entity_config.get('x', 0),
                y=entity_config.get('y', 0),
                entity_id=entity_config.get('id')
            )
            sim.add_entity(entity)
    
    # 6. Register triggers
    for trigger in scenario_data.get('triggers', []):
        tick = trigger.get('tick', 0)
        action = create_action(trigger.get('action', {}))
        if action:
            sim.triggers.setdefault(tick, []).append({
                'entity_id': trigger['entity'],
                'action': action
            })
    
    # 7. Run simulation (uses the same loop as normal matches)
    history = sim.simulate()
    return {
        'history': history,
        'static_grid': sim.nav_grid.static_grid,
        'width': sim.map_data.width,
        'height': sim.map_data.height,
        'tick_duration': sim.tick_duration
    }


def run_scenario_from_file(yaml_path):
    """Load and execute a scenario from a YAML file path."""
    scenario_data = load_scenario_yaml(yaml_path)
    return execute_scenario(scenario_data)

