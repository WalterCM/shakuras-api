import uuid
import random
import json
import math
from .data import UNIT_STATS
from .utils import Vector2D
from .actions import GatherAction, AttackAction, MoveAction, HoldAction

class Map:
    """Stores static map data: dimensions, spawns, and terrain."""
    def __init__(self, name="Default", width=128, height=128, spawn_points=None):
        self.name = name
        self.width = width
        self.height = height
        # Default spawns if none provided
        self.spawn_points = spawn_points or {
            'p1': Vector2D(10, 10),
            'p2': Vector2D(width - 10, height - 10)
        }
        # Placeholder for terrain (0 = walkable, 1 = obstacle)
        self.terrain = [[0 for _ in range(width)] for _ in range(height)]

class SpatialGrid:
    """Optimizes proximity lookups for collisions and targeting."""
    def __init__(self, width, height, cell_size=8.0):
        self.cell_size = cell_size
        self.cols = math.ceil(width / cell_size)
        self.rows = math.ceil(height / cell_size)
        self.grid = {} # (col, row) -> [entity_ids]

    def _get_cell(self, pos):
        col = int(pos.x / self.cell_size)
        row = int(pos.y / self.cell_size)
        return (col, row)

    def clear(self):
        self.grid = {}

    def insert(self, entity):
        cell = self._get_cell(entity.pos)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(entity.id)

    def get_nearby_ids(self, pos):
        """Returns entity IDs in the current and 8 surrounding cells."""
        cx, cy = self._get_cell(pos)
        nearby = []
        for i in range(-1, 2):
            for j in range(-1, 2):
                cell = (cx + i, cy + j)
                if cell in self.grid:
                    nearby.extend(self.grid[cell])
        return nearby

class Entity:
    """Represents a single unit or building in the game world"""
    def __init__(self, unit_type, owner_id, x, y, entity_id=None):
        self.id = entity_id or str(uuid.uuid4())[:8]
        self.type = unit_type
        self.owner_id = owner_id
        self.pos = Vector2D(x, y)
        self.status = 'idle' # idle, move, attack, harvest, dead, return
        self.action = None  # Current action (GatherAction, AttackAction, etc.)
        self.target_id = None  # Kept for backward compatibility
        self.destination = None  # Kept for backward compatibility
        self.carrying = 0
        self.last_patch_id = None
        self.production_queue = []
        self.production_progress = 0
        
        # Load stats from data.py
        stats = UNIT_STATS.get(unit_type, UNIT_STATS['worker'])
        self.hp = stats['hp']
        self.max_hp = stats.get('max_hp', stats['hp'])
        self.damage = stats['damage']
        self.range = stats['range']
        self.cooldown = stats['cooldown']
        self.speed = stats['speed']
        self.harvest_time = stats.get('harvest_time', 0)
        self.harvest_amount = stats.get('harvest_amount', 0)
        self.radius = stats.get('radius', 1.0)
        self.width = stats.get('width', 1)
        self.height = stats.get('height', 1)
        self.current_cooldown = 0
        
        # Resource contention tracking
        self.occupied_by = None  # For mineral patches: ID of worker currently mining

    def get_current_status(self):
        """Returns the status string from the current action or default"""
        if self.action:
            return self.action.get_status()
        return self.status

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'owner_id': self.owner_id,
            'x': round(self.pos.x, 2),
            'y': round(self.pos.y, 2),
            'hp': round(self.hp, 2),
            'status': self.get_current_status(),
            'carrying': self.carrying,
            'prod_queue': self.production_queue,
            'prod_progress': self.production_progress,
            'radius': self.radius,
            'width': self.width,
            'height': self.height
        }

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.status = 'dead'
            self.action = None # Stop current behavior
            self.carrying = 0 # Drop minerals on death
            self.production_queue = [] # Cancel production

    def update(self, game_state):
        """Update entity state based on current logic"""
        if self.status == 'dead':
            return

        # Tick down cooldown
        if self.current_cooldown > 0:
            self.current_cooldown -= 1

        # Execute current action
        if self.action:
            self.action.update(self, game_state)
        
        if self.production_queue:
            self._handle_production(game_state)
            
        # 3. Soft Collision (Repulsion)
        # We only apply this to moving units or if they are overlapping
        # Workers ignore collision while mining (at the patch)
        from .actions import GatherAction
        is_mining = isinstance(self.action, GatherAction) and self.action.phase == 'mining'
        if self.type not in ['base', 'mineral_patch'] and not is_mining:
            self._apply_repulsion(game_state)

    def _apply_repulsion(self, game_state):
        """Pushes away from nearby entities to prevent overlapping"""
        nearby_ids = game_state.grid.get_nearby_ids(self.pos)
        
        # Pre-calculate my radius to avoid repeated access if significant
        my_radius = self.radius
        
        for other_id in nearby_ids:
            if other_id == self.id:
                continue
            other = game_state.entities.get(other_id)
            if not other or other.status == 'dead':
                continue
                
            # If both are buildings, they don't push each other
            if self.type in ['base', 'mineral_patch'] and other.type in ['base', 'mineral_patch']:
                continue

            diff = self.pos - other.pos
            dist_sq = diff.length_sq()
            min_dist = my_radius + other.radius
            
            if dist_sq < min_dist**2:
                # Push factor (softness)
                # Buildings push units VERY strongly
                push_factor = 0.8 if other.type in ['base', 'mineral_patch', 'building'] else 0.2
                
                if dist_sq > 0.001:
                    dist = math.sqrt(dist_sq)
                    overlap = min_dist - dist
                    # Directly adjust pos to save on Vector2D creation if needed, 
                    # but normalize returns a new vector anyway.
                    push = diff.normalize() * (overlap * push_factor)
                    self.pos += push
                else:
                    # Deterministic push for perfectly stacked units
                    angle = (hash(self.id + other_id) % 360) * (math.pi / 180)
                    push_dist = min_dist * push_factor
                    self.pos.x += math.cos(angle) * push_dist
                    self.pos.y += math.sin(angle) * push_dist


    def _handle_production(self, game_state):
        unit_type = self.production_queue[0]
        stats = UNIT_STATS.get(unit_type)
        build_time = stats['build_time']
        
        self.production_progress += 1
        
        if self.production_progress >= build_time:
            # Spawn unit just outside the building's radius
            # We use a slight offset of 1.0 beyond the radius
            spawn_dist = self.radius + stats.get('radius', 1.0) + 1.0
            new_unit = Entity(unit_type, self.owner_id, self.pos.x, self.pos.y + spawn_dist)
            game_state._spawn_entity(new_unit)
            
            # Clean up queue
            self.production_queue.pop(0)
            self.production_progress = 0


class ProductionAI:
    """Manages simple automated production for a player"""
    def __init__(self, player_id):
        self.player_id = player_id

    def update(self, simulator):
        # We only want workers now
        if simulator.resources[self.player_id] >= 50:
            simulator.request_unit(self.player_id, 'worker')

class MatchSimulator:
    """Handles the simulation loop of a match using JSON Deltas for efficiency"""
    def __init__(self, player1, player2, map_instance=None, max_ticks=100):
        self.player1 = player1
        self.player2 = player2
        # Use string IDs for consistency with visualizer
        self.player1_id = 'p1'
        self.player2_id = 'p2'
        
        # Load from Map instance or use defaults
        if map_instance:
            self.map_data = map_instance
        else:
            # Fallback for compatibility/tests
            from .models import Map
            self.map_data = Map(
                width=128, 
                height=128, 
                spawn_points={'p1': {'x': 10, 'y': 10}, 'p2': {'x': 118, 'y': 118}},
                minerals=[]
            )

        self.max_ticks = max_ticks
        self.entities = {} # Use dict for fast lookup by ID
        self.history = [] # Stores deltas
        self.resources = {
            self.player1_id: 50.0,
            self.player2_id: 50.0
        }
        self.grid = SpatialGrid(self.map_data.width, self.map_data.height)
        self.ai_controllers = [
            ProductionAI(self.player1_id),
            ProductionAI(self.player2_id)
        ]

    def add_minerals(self, player_id, amount):
        if player_id in self.resources:
            self.resources[player_id] += amount

    def request_unit(self, player_id, unit_type):
        """Attempts to queue a unit for production"""
        stats = UNIT_STATS.get(unit_type)
        if not stats or self.resources[player_id] < stats['cost']:
            return False
            
        # Find an appropriate production building (just 'base' for now)
        bases = [e for e in self.entities.values() 
                 if e.owner_id == player_id and e.type == 'base' and e.status != 'dead']
        
        if not bases:
            return False
            
        # Add to the base with the shortest queue
        best_base = min(bases, key=lambda b: len(b.production_queue))
        
        if len(best_base.production_queue) < 5: # Max queue length
            self.resources[player_id] -= stats['cost']
            best_base.production_queue.append(unit_type)
            return True
            
        return False

    def _spawn_entity(self, entity):
        self.entities[entity.id] = entity
        
        # Assign default actions to newly spawned units
        if entity.type == 'worker':
            # Workers harvest from nearest patch
            patches = [e for e in self.entities.values() 
                      if e.type == 'mineral_patch' and e.hp > 0]
            if patches:
                closest = min(patches, key=lambda p: entity.pos.dist_to_sq(p.pos))
                entity.action = GatherAction(closest.id)
        
        elif entity.type in ['marine', 'zealot', 'zergling']:
            # Combat units attack nearest enemy
            enemies = [e for e in self.entities.values()
                      if e.owner_id != entity.owner_id and e.owner_id != 'neutral'
                      and e.status != 'dead' and e.type != 'mineral_patch']
            if enemies:
                closest = min(enemies, key=lambda e: entity.pos.dist_to_sq(e.pos))
                entity.action = AttackAction(closest.id)

    def _setup_initial_entities(self):
        # 1. Minerals FIRST from Map data so workers can find them
        for m in self.map_data.minerals:
            patch = Entity('mineral_patch', 'neutral', m['x'], m['y'])
            # Center it: (x, y) from editor is top-left
            patch.pos.x += patch.width / 2.0
            patch.pos.y += patch.height / 2.0
            self._spawn_entity(patch)

        # 2. Spawns (Bases)
        spawns = self.map_data.spawn_points
        for pid, pos in spawns.items():
            base = Entity('base', pid, pos['x'], pos['y'])
            # Center it: (x, y) from editor is top-left
            base.pos.x += base.width / 2.0
            base.pos.y += base.height / 2.0
            self._spawn_entity(base)
            
            # 3. Initial workers near base (spawned AFTER minerals)
            # Spawn them in a cluster around the base center
            bx, by = base.pos.x, base.pos.y
            offsets = [(2.5, 0), (-2.5, 0), (0, 2), (0, -2)] 
            for i in range(4):
                ox, oy = offsets[i]
                self._spawn_entity(Entity('worker', pid, bx + ox, by + oy))

    def _add_entity(self, entity):
        self.entities[entity.id] = entity

    def simulate(self):
        """Runs the simulation and returns delta-based JSON history"""
        self._setup_initial_entities()
        
        # Initial State (Tick 0)
        initial_state = [e.to_dict() for e in self.entities.values()]
        self.history.append({
            'tick': 0, 
            'map': {'width': self.map_data.width, 'height': self.map_data.height},
            'entities': initial_state,
            'resources': self.resources.copy()
        })

        for tick in range(1, self.max_ticks):
            # 1. Update Controllers
            for ai in self.ai_controllers:
                ai.update(self)

            # 2. Prepare Spatial Search
            self.grid.clear()
            for ent in self.entities.values():
                if ent.status != 'dead':
                    self.grid.insert(ent)

            # 3. Capture Snapshots for delta calculation
            pre_update_snapshots = {eid: ent.to_dict() for eid, ent in self.entities.items()}
            old_resources = self.resources.copy()
            old_entity_ids = set(self.entities.keys())

            # 4. Physics/Behavior Update
            for ent in list(self.entities.values()):
                ent.update(self)

            # 5. Record Deltas
            tick_deltas = []
            for ent_id, ent in self.entities.items():
                if ent_id not in old_entity_ids:
                    # New entity spawned
                    tick_deltas.append(ent.to_dict())
                else:
                    # Existing entity - calculate delta
                    old_snapshot = pre_update_snapshots[ent_id]
                    new_snapshot = ent.to_dict()
                    delta = {'id': ent_id}
                    changed = False
                    
                    for key, val in new_snapshot.items():
                        if key == 'id': continue
                        old_val = old_snapshot.get(key)
                        
                        # Use tolerance for floats
                        if isinstance(val, (int, float)) and isinstance(old_val, (int, float)):
                            if abs(val - old_val) > 0.01:
                                delta[key] = val
                                changed = True
                        elif val != old_val:
                            delta[key] = val
                            changed = True
                    
                    if changed:
                        tick_deltas.append(delta)
            
            # Record Resource Deltas
            res_delta = {pid: round(amount, 1) for pid, amount in self.resources.items() 
                         if abs(amount - old_resources[pid]) > 0.1}

            if tick_deltas or res_delta:
                entry = {'tick': tick}
                if tick_deltas: entry['entities'] = tick_deltas
                if res_delta: entry['resources'] = res_delta
                self.history.append(entry)

        return self.history
