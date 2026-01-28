import uuid
import random
import json
import math
from .data import UNIT_STATS
from .utils import Vector2D

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
        self.target_id = None
        self.destination = None
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
        self.current_cooldown = 0

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'owner_id': self.owner_id,
            'x': round(self.pos.x, 2),
            'y': round(self.pos.y, 2),
            'hp': round(self.hp, 2),
            'status': self.status,
            'carrying': self.carrying,
            'prod_queue': self.production_queue,
            'prod_progress': self.production_progress,
            'radius': self.radius
        }

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.status = 'dead'
            self.carrying = 0 # Drop minerals on death
            self.production_queue = [] # Cancel production

    def update(self, game_state):
        """Update entity state based on current logic"""
        if self.status == 'dead':
            return

        if self.current_cooldown > 0:
            self.current_cooldown -= 1

        # 1. Action-based Movement/Logic
        if self.status == 'move' and self.destination:
            self._handle_move()
        elif self.status == 'attack' and self.target_id:
            self._handle_attack(game_state)
        elif self.status == 'harvest' and self.target_id:
            self._handle_harvest(game_state)
        elif self.status == 'return':
            self._handle_return(game_state)
        
        if self.production_queue:
            self._handle_production(game_state)
            
        # 3. Soft Collision (Repulsion)
        # We only apply this to moving units or if they are overlapping
        # Workers ignore collision while harvesting or returning (standard SC mechanic)
        if self.type not in ['base', 'mineral_patch'] and self.status not in ['harvest', 'return']:
            self._apply_repulsion(game_state)

    def _apply_repulsion(self, game_state):
        """Pushes away from nearby entities to prevent overlapping"""
        nearby_ids = game_state.grid.get_nearby_ids(self.pos)
        
        for other_id in nearby_ids:
            if other_id == self.id:
                continue
            other = game_state.entities.get(other_id)
            if not other or other.status == 'dead':
                continue
                
            diff = self.pos - other.pos
            dist_sq = diff.length_sq()
            min_dist = self.radius + other.radius
            
            if dist_sq < min_dist**2 and dist_sq > 0.001:
                dist = math.sqrt(dist_sq)
                overlap = min_dist - dist
                
                # Push factor (softness)
                # Buildings push units VERY strongly to keep them out of the floorplan
                push_factor = 0.8 if other.type in ['base', 'mineral_patch', 'building'] else 0.2
                
                # Move slightly away
                push = diff.normalize() * (overlap * push_factor)
                self.pos += push

    def _handle_move(self):
        target = Vector2D(*self.destination)
        diff = target - self.pos
        dist = diff.length()

        if dist < self.speed:
            self.pos = target
            self.status = 'idle'
            self.destination = None
        else:
            self.pos += diff.normalize() * self.speed

    def _handle_attack(self, game_state):
        target = game_state.entities.get(self.target_id)
        if not target or target.status == 'dead':
            self.status = 'idle'
            self.target_id = None
            return

        diff = target.pos - self.pos
        dist = diff.length()

        if dist <= self.range:
            if self.current_cooldown <= 0:
                target.take_damage(self.damage)
                self.current_cooldown = self.cooldown
        else:
            # Move towards target
            move_dist = min(self.speed, dist - self.range + 0.1)
            self.pos += diff.normalize() * move_dist

    def _handle_harvest(self, game_state):
        patch = game_state.entities.get(self.target_id)
        if not patch or patch.hp <= 0:
            self.status = 'idle'
            self.target_id = None
            return

        diff = patch.pos - self.pos
        dist = diff.length()

        if dist <= self.range:
            if self.current_cooldown <= 0:
                # Actual mining time
                patch.hp -= self.harvest_amount
                self.carrying = self.harvest_amount
                self.last_patch_id = patch.id
                self.status = 'return'
                self.current_cooldown = self.harvest_time # Mining duration
        else:
            # Move towards patch
            move_dist = min(self.speed, dist - self.range + 0.1)
            self.pos += diff.normalize() * move_dist

    def _handle_return(self, game_state):
        # Move back to nearest base
        bases = [e for e in game_state.entities.values() 
                 if e.owner_id == self.owner_id and e.type == 'base']
        if not bases:
            self.status = 'idle'
            return
            
        # Find closest base
        closest_base = min(bases, key=lambda b: self.pos.dist_to_sq(b.pos))
        
        diff = closest_base.pos - self.pos
        dist = diff.length()
        
        if dist <= self.range:
            if self.current_cooldown <= 0:
                # Deposit minerals
                game_state.add_minerals(self.owner_id, self.carrying)
                self.carrying = 0
                self.status = 'harvest'
                self.target_id = self.last_patch_id
        else:
            # Move towards base
            move_dist = min(self.speed, dist - self.range + 0.1)
            self.pos += diff.normalize() * move_dist

    def _handle_production(self, game_state):
        unit_type = self.production_queue[0]
        stats = UNIT_STATS.get(unit_type)
        build_time = stats['build_time']
        
        self.production_progress += 1
        
        if self.production_progress >= build_time:
            # Spawn unit just outside the building's radius (using an offset)
            # Offset is relative to the base center
            new_unit = Entity(unit_type, self.owner_id, self.pos.x, self.pos.y + 5)
            game_state._spawn_entity(new_unit)
            
            # Clean up queue
            self.production_queue.pop(0)
            self.production_progress = 0

class MatchSimulator:
    """Handles the simulation loop of a match using JSON Deltas for efficiency"""
    def __init__(self, player1, player2, map_data=None, max_ticks=100):
        self.player1 = player1
        self.player2 = player2
        self.map = map_data or Map()
        self.max_ticks = max_ticks
        self.entities = {} # Use dict for fast lookup by ID
        self.history = [] # Stores deltas
        self.resources = {
            self.player1.id: 50.0,
            self.player2.id: 50.0
        }
        self.grid = SpatialGrid(self.map.width, self.map.height)

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

    def _setup_initial_entities(self):
        # Bases at fixed spawn points
        p1_spawn = self.map.spawn_points.get('p1', Vector2D(10, 10))
        p2_spawn = self.map.spawn_points.get('p2', Vector2D(self.map.width-10, self.map.height-10))
        
        self._add_entity(Entity('base', self.player1.id, p1_spawn.x, p1_spawn.y))
        self._add_entity(Entity('base', self.player2.id, p2_spawn.x, p2_spawn.y))
        
        # Mineral Patches near bases (Relative to spawn)
        self._add_entity(Entity('mineral_patch', 'neutral', p1_spawn.x - 5, p1_spawn.y + 15))
        self._add_entity(Entity('mineral_patch', 'neutral', p1_spawn.x + 15, p1_spawn.y - 5))
        
        self._add_entity(Entity('mineral_patch', 'neutral', p2_spawn.x + 5, p2_spawn.y - 15))
        self._add_entity(Entity('mineral_patch', 'neutral', p2_spawn.x - 15, p2_spawn.y + 5))
        
        # Workers
        for i in range(4):
            self._add_entity(Entity('worker', self.player1.id, p1_spawn.x + 5 + i, p1_spawn.y + 5))
            self._add_entity(Entity('worker', self.player2.id, p2_spawn.x - 5 - i, p2_spawn.y - 5))

    def _add_entity(self, entity):
        self.entities[entity.id] = entity

    def simulate(self):
        """Runs the simulation and returns delta-based JSON history"""
        self._setup_initial_entities()
        
        # Assign workers to harvest
        patches = [e for e in self.entities.values() if e.type == 'mineral_patch']
        
        for ent in self.entities.values():
            if ent.type == 'worker':
                # Find closest patch
                closest = min(patches, key=lambda p: ent.pos.dist_to_sq(p.pos))
                ent.status = 'harvest'
                ent.target_id = closest.id

        # Initial State (Tick 0)
        initial_state = [e.to_dict() for e in self.entities.values()]
        self.history.append({
            'tick': 0, 
            'map': {'width': self.map.width, 'height': self.map.height},
            'entities': initial_state,
            'resources': self.resources.copy()
        })

        for tick in range(1, self.max_ticks):
            tick_deltas = []
            
            # Simple Production AI
            for pid in [self.player1.id, self.player2.id]:
                if self.resources[pid] >= 100:
                    # Alternating between workers and marines
                    unit_type = 'marine' if random.random() > 0.3 else 'worker'
                    self.request_unit(pid, unit_type)

            # Update Grid
            self.grid.clear()
            for ent in self.entities.values():
                if ent.status != 'dead':
                    self.grid.insert(ent)

            # Snapshots (capture ALL entities including new ones)
            pre_update = {}
            for eid, ent in self.entities.items():
                pre_update[eid] = (ent.pos.x, ent.pos.y, ent.hp, ent.status, ent.carrying, list(ent.production_queue), ent.production_progress)
            
            old_resources = self.resources.copy()
            old_entity_ids = set(self.entities.keys())

            # Update
            for ent in list(self.entities.values()):
                ent.update(self)

            # Record Entity Deltas and New Entities
            for ent_id, ent in self.entities.items():
                if ent_id not in old_entity_ids:
                    # New Entity spawned this tick
                    tick_deltas.append(ent.to_dict())
                    continue

                old_x, old_y, old_hp, old_status, old_carrying, old_q, old_prog = pre_update[ent_id]
                
                if (abs(ent.pos.x - old_x) > 0.01 or 
                    abs(ent.pos.y - old_y) > 0.01 or 
                    abs(ent.hp - old_hp) > 0.01 or 
                    ent.status != old_status or
                    ent.carrying != old_carrying or
                    ent.production_queue != old_q or
                    ent.production_progress != old_prog):
                    
                    delta = {'id': ent_id}
                    if abs(ent.pos.x - old_x) > 0.01: delta['x'] = round(ent.pos.x, 2)
                    if abs(ent.pos.y - old_y) > 0.01: delta['y'] = round(ent.pos.y, 2)
                    if abs(ent.hp - old_hp) > 0.01: delta['hp'] = round(ent.hp, 2)
                    if ent.status != old_status: delta['status'] = ent.status
                    if ent.carrying != old_carrying: delta['carrying'] = ent.carrying
                    if ent.production_queue != old_q: delta['prod_queue'] = ent.production_queue
                    if ent.production_progress != old_prog: delta['prod_progress'] = ent.production_progress
                    
                    tick_deltas.append(delta)
            
            # Record Resource Deltas
            res_delta = {}
            for pid, amount in self.resources.items():
                if abs(amount - old_resources[pid]) > 0.1:
                    res_delta[pid] = round(amount, 1)

            if tick_deltas or res_delta:
                entry = {'tick': tick}
                if tick_deltas: entry['entities'] = tick_deltas
                if res_delta: entry['resources'] = res_delta
                self.history.append(entry)

        return self.history
