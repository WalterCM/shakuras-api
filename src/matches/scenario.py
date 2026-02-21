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
        minerals=[],  # Minerals now come from entities
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


def execute_scenario(scenario_data):
    """
    Execute a scenario and return the replay history.
    
    Args:
        scenario_data: Dict with scenario/map configuration
    
    Returns:
        List of tick deltas (replay history)
    """
    # Create EngineMap from config
    engine_map = create_engine_map_from_config(scenario_data)
    
    # Create simulator without players
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
    
    # Disable AI controllers for scenarios
    sim.ai_controllers = []
    
    # Clear entities - we'll create from config
    sim.entities = {}
    entities_by_id = {}
    
    # Get entities from config
    entities_config = scenario_data.get('entities', [])
    
    # Create all entities from config
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
        
        # Center minerals (they are placed at top-left)
        if entity.type == 'mineral_patch':
            entity.pos.x += entity.width / 2.0
            entity.pos.y += entity.height / 2.0
            
            # Add to nav grid
            bx, by = int(entity.pos.x - entity.width/2), int(entity.pos.y - entity.height/2)
            for ox in range(entity.width):
                for oy in range(entity.height):
                    sim.nav_grid.set_static(bx + ox, by + oy, entity.id)
        
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
    return execute_scenario(scenario_data)
