"""
Scenario loader and executor.
Loads YAML scenarios and executes them using the MatchSimulator.
"""
import os
import yaml
from pathlib import Path
from matches.engine import MatchSimulator, Entity, Map as EngineMap
from matches.models import Map as MapModel
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


def load_map_from_db(map_name):
    """Load map configuration from database by name."""
    try:
        map_model = MapModel.objects.get(name__iexact=map_name)
        return {
            'name': map_model.name,
            'width': map_model.width,
            'height': map_model.height,
            'spawn_points': map_model.spawn_points,
            'minerals': map_model.minerals,
        }
    except MapModel.DoesNotExist:
        return None


def create_engine_map_from_config(map_config):
    """Create an Engine Map from map configuration dict."""
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
        minerals=map_config.get('minerals', []),
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


def execute_scenario(scenario_data, map_data=None):
    """
    Execute a scenario and return the replay history.
    
    Args:
        scenario_data: Dict with scenario configuration
        map_data: Optional map config from DB (if base_map specified)
    
    Returns:
        List of tick deltas (replay history)
    """
    # Get map config
    if map_data:
        engine_map = create_engine_map_from_config(map_data)
    else:
        # Default map if no base_map specified
        engine_map = EngineMap()
    
    # Create simulator without players (we'll create entities manually)
    class DummyPlayer:
        def __init__(self, id):
            self.id = id
            self.nickname = id
    
    sim = MatchSimulator(
        DummyPlayer('p1'),
        DummyPlayer('p2'),
        map_instance=engine_map,
        max_ticks=scenario_data.get('config', {}).get('max_ticks', 100)
    )
    
    # Disable AI controllers (no auto-production)
    sim.ai_controllers = []
    
    # Don't setup initial entities (bases, workers) - we define our own
    # Clear the entities that were created by _setup_initial_entities
    sim.entities = {}
    
    # Create entities from scenario
    entities_by_id = {}
    
    # First: Create mineral patches from base map
    for mineral in engine_map.minerals:
        entity = Entity(
            unit_type='mineral_patch',
            owner_id='neutral',
            x=mineral.get('x', 0),
            y=mineral.get('y', 0),
        )
        # Center it: (x, y) is top-left
        entity.pos.x += entity.width / 2.0
        entity.pos.y += entity.height / 2.0
        entities_by_id[entity.id] = entity
        sim.entities[entity.id] = entity
        
        # Add to nav grid
        bx, by = int(entity.pos.x - entity.width/2), int(entity.pos.y - entity.height/2)
        for ox in range(entity.width):
            for oy in range(entity.height):
                sim.nav_grid.set_static(bx + ox, by + oy, entity.id)
    
    # Second: Create extra minerals from scenario
    for entity_config in scenario_data.get('entities', []):
        if 'extra_minerals' in entity_config:
            for mineral in entity_config['extra_minerals']:
                entity = Entity(
                    unit_type='mineral_patch',
                    owner_id='neutral',
                    x=mineral.get('x', 0),
                    y=mineral.get('y', 0),
                )
                entity.pos.x += entity.width / 2.0
                entity.pos.y += entity.height / 2.0
                entities_by_id[entity.id] = entity
                sim.entities[entity.id] = entity
                
                bx, by = int(entity.pos.x - entity.width/2), int(entity.pos.y - entity.height/2)
                for ox in range(entity.width):
                    for oy in range(entity.height):
                        sim.nav_grid.set_static(bx + ox, by + oy, entity.id)
    
    # Third: Create other entities from scenario (workers, units, etc)
    for entity_config in scenario_data.get('entities', []):
        if 'type' not in entity_config:
            continue
        
        entity = Entity(
            unit_type=entity_config['type'],
            owner_id=entity_config['owner'],
            x=entity_config['x'],
            y=entity_config['y'],
            entity_id=entity_config.get('id')
        )
        entities_by_id[entity.id] = entity
        sim.entities[entity.id] = entity
    
    # Prepare triggers indexed by tick
    triggers_by_tick = {}
    for trigger in scenario_data.get('triggers', []):
        tick = trigger.get('tick', 0)
        if tick not in triggers_by_tick:
            triggers_by_tick[tick] = []
        triggers_by_tick[tick].append(trigger)
    
    # Get max_ticks from config
    max_ticks = scenario_data.get('config', {}).get('max_ticks', 100)
    
    # Initial state (tick 0)
    initial_state = [e.to_dict(sim) for e in sim.entities.values()]
    sim.history.append({
        'tick': 0,
        'map': {'width': engine_map.width, 'height': engine_map.height},
        'entities': initial_state,
        'resources': sim.resources.copy()
    })
    
    # Execute triggers at tick 0
    for trigger in triggers_by_tick.get(0, []):
        entity_id = trigger.get('entity')
        action_config = trigger.get('action', {})
        if entity_id in entities_by_id and action_config:
            action = create_action(action_config)
            if action:
                entities_by_id[entity_id].action = action
    
    # Simulation loop
    for tick in range(1, max_ticks + 1):
        # Execute triggers for this tick
        for trigger in triggers_by_tick.get(tick, []):
            entity_id = trigger.get('entity')
            action_config = trigger.get('action', {})
            if entity_id in entities_by_id and action_config:
                action = create_action(action_config)
                if action:
                    entities_by_id[entity_id].action = action
        
        # Prepare grids
        sim.grid.clear()
        sim.nav_grid.clear_dynamic()
        
        for ent in sim.entities.values():
            if ent.status != 'dead':
                sim.grid.insert(ent)
                if ent.type not in ['base', 'mineral_patch']:
                    sim.nav_grid.set_dynamic(ent.pos.x, ent.pos.y, ent.id)
        
        # Capture snapshots for delta
        pre_update_snapshots = {eid: ent.to_dict(sim) for eid, ent in sim.entities.items()}
        
        # Update entities
        for ent in list(sim.entities.values()):
            ent.update(sim)
        
        # Record deltas
        tick_deltas = []
        for ent_id, ent in sim.entities.items():
            old_snapshot = pre_update_snapshots.get(ent_id)
            if old_snapshot:
                new_snapshot = ent.to_dict(sim)
                delta = {'id': ent_id}
                changed = False
                
                for key, val in new_snapshot.items():
                    if key == 'id':
                        continue
                    old_val = old_snapshot.get(key)
                    
                    if isinstance(val, (int, float)) and isinstance(old_val, (int, float)):
                        if abs(val - old_val) > 0.01:
                            delta[key] = val
                            changed = True
                    elif val != old_val:
                        delta[key] = val
                        changed = True
                
                if changed:
                    tick_deltas.append(delta)
            else:
                # New entity
                tick_deltas.append(ent.to_dict(sim))
        
        if tick_deltas:
            sim.history.append({
                'tick': tick,
                'entities': tick_deltas
            })
    
    return sim.history


def run_scenario_from_file(yaml_path):
    """Load and execute a scenario from a YAML file path."""
    scenario_data = load_scenario_yaml(yaml_path)
    
    # Get base map from DB if specified
    map_data = None
    if 'base_map' in scenario_data:
        map_data = load_map_from_db(scenario_data['base_map'])
    
    return execute_scenario(scenario_data, map_data)
