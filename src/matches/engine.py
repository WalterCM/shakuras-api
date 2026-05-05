import uuid
import random
import json
import math
from .loader import UNIT_DEFINITIONS
from .utils import Vector2D
from .pathfinding import AStarPathfinder
from .actions import GatherAction, AttackAction, MoveAction, HoldAction

class Map:
    """Stores static map data: dimensions, spawns, and terrain."""
    def __init__(self, name="Default", width=128, height=128, spawn_points=None, minerals=None, entities=None):
        self.name = name
        self.width = width
        self.height = height
        # Default spawns if none provided
        self.spawn_points = spawn_points or {
            'p1': Vector2D(10, 10),
            'p2': Vector2D(width - 10, height - 10)
        }
        # List of {x, y} for mineral patches (legacy format)
        self.minerals = minerals or []
        # List of entity dicts from YAML (type, owner, x, y, id)
        self.entities = entities or []
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
        """Registers entity in all cells it overlaps with its rectangular dimensions."""
        x1 = int((entity.pos.x - entity.width/2) / self.cell_size)
        y1 = int((entity.pos.y - entity.height/2) / self.cell_size)
        x2 = int((entity.pos.x + entity.width/2) / self.cell_size)
        y2 = int((entity.pos.y + entity.height/2) / self.cell_size)
        
        for col in range(x1, x2 + 1):
            for row in range(y1, y2 + 1):
                cell = (col, row)
                if cell not in self.grid:
                    self.grid[cell] = []
                self.grid[cell].append(entity.id)

    def get_nearby_ids(self, pos):
        """Returns UNIQUE entity IDs in the current and 8 surrounding cells."""
        cx, cy = self._get_cell(pos)
        nearby = set()
        for i in range(-1, 2):
            for j in range(-1, 2):
                cell = (cx + i, cy + j)
                if cell in self.grid:
                    for eid in self.grid[cell]:
                        nearby.add(eid)
        return list(nearby)

class NavigationGrid:
    """Handles tile-based occupancy for pathfinding and collision avoidance."""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        # Layer A: Static (Buildings/Minerals)
        self.static_grid = [[None for _ in range(height)] for _ in range(width)]
        # Layer B: Dynamic (Units)
        self.dynamic_grid = [[None for _ in range(height)] for _ in range(width)]

    def is_blocked(self, pos, check_dynamic=True, entity=None):
        """Checks if a point is blocked by static or dynamic objects."""
        x, y = int(pos.x), int(pos.y)
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return True # Edge of map
        
        # Static Layer (Buildings/Minerals)
        if self.static_grid[x][y] and (not entity or self.static_grid[x][y] != entity.id):
            return True
        
        # Dynamic Layer (Units)
        if check_dynamic and self.dynamic_grid[x][y] and (not entity or self.dynamic_grid[x][y] != entity.id):
            return True
        return False
    
    def is_area_blocked(self, x, y, width, height, check_dynamic=True, entity=None, eps=0.2, ignore_static_id=None):
        """Checks if a rectangular area is partially or fully blocked."""
        x1, y1 = math.floor(x - width/2 + eps), math.floor(y - height/2 + eps)
        x2, y2 = math.floor(x + width/2 - eps), math.floor(y + height/2 - eps)
        for ox in range(x1, x2 + 1):
            for oy in range(y1, y2 + 1):
                if ox < 0 or ox >= self.width or oy < 0 or oy >= self.height:
                    return True
                if self.static_grid[ox][oy] and (not entity or self.static_grid[ox][oy] != entity.id):
                    # Check if we should ignore this specific static obstacle
                    if ignore_static_id and self.static_grid[ox][oy] == ignore_static_id:
                        continue
                    return True
                if check_dynamic and self.dynamic_grid[ox][oy] and (not entity or self.dynamic_grid[ox][oy] != entity.id):
                    return True
        return False

    def clear_dynamic(self):
        for x in range(self.width):
            for y in range(self.height):
                self.dynamic_grid[x][y] = None

    def set_static_rect(self, x, y, width, height, entity_id):
        x1, y1 = math.floor(x - width/2 + 0.01), math.floor(y - height/2 + 0.01)
        x2, y2 = math.floor(x + width/2 - 0.01), math.floor(y + height/2 - 0.01)
        for ox in range(x1, x2 + 1):
            for oy in range(y1, y2 + 1):
                if 0 <= ox < self.width and 0 <= oy < self.height:
                    self.static_grid[ox][oy] = entity_id

    def set_static(self, x, y, entity_id):
        """Legacy/Single-tile alias"""
        self.set_static_rect(x, y, 1, 1, entity_id)

    def set_dynamic_rect(self, x, y, width, height, entity_id):
        x1, y1 = math.floor(x - width/2 + 0.01), math.floor(y - height/2 + 0.01)
        x2, y2 = math.floor(x + width/2 - 0.01), math.floor(y + height/2 - 0.01)
        for ox in range(x1, x2 + 1):
            for oy in range(y1, y2 + 1):
                if 0 <= ox < self.width and 0 <= oy < self.height:
                    self.dynamic_grid[ox][oy] = entity_id

    def set_dynamic(self, x, y, entity_id):
        """Legacy/Single-tile alias"""
        self.set_dynamic_rect(x, y, 1, 1, entity_id)

    def get_obstacle_at(self, pos):
        x, y = int(pos.x), int(pos.y)
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.static_grid[x][y] or self.dynamic_grid[x][y]
        return None

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
        self.waypoints = [] # For A* pathfinding
        
        # Load definitions from YAML
        self.definition = UNIT_DEFINITIONS.get(unit_type, {})
        self.speed = self.definition.get('speed', 0)
        self.hp = self.definition.get('hp', 100)
        self.max_hp = self.definition.get('max_hp', self.hp)
        self.damage = self.definition.get('damage', 0)
        self.range = self.definition.get('range', 1.0)
        self.cooldown = self.definition.get('cooldown', 20)
        self.speed = self.definition.get('speed', 0)
        self.harvest_time = self.definition.get('harvest_time', 0)
        self.harvest_amount = self.definition.get('harvest_amount', 0)
        self.width = self.definition.get('width', 1.0)
        self.height = self.definition.get('height', 1.0)
        self.current_cooldown = 0
        
        # Resource contention tracking
        self.occupied_by = None  # For mineral patches: ID of scv currently mining
        
        # Collision & Navigation
        self.pos_memory = []
        self.ghost_mode_ticks = 0
        self.slide_direction = None # None, 'left', or 'right'
        self.last_slide_normal = None

    def get_current_status(self, game_state=None):
        """Returns the status string from the current action or default"""
        if self.status == 'dead':
            return 'dead'
        if self.action:
            try:
                # Some actions might not take game_state yet, but GatherAction does
                # Only pass game_state if it's not None
                if game_state is not None:
                    return self.action.get_status(self, game_state)
                else:
                    return self.action.get_status()
            except (TypeError, AttributeError):
                # Action doesn't support get_status or requires different args
                return self.status
        return self.status

    @property
    def radius(self):
        """Backward compatibility: Approximate radius from width/height"""
        return (self.width + self.height) / 4.0

    def to_dict(self, game_state=None):
        return {
            'id': self.id,
            'type': self.type,
            'owner_id': self.owner_id,
            'x': round(self.pos.x, 2),
            'y': round(self.pos.y, 2),
            'hp': round(self.hp, 2),
            'max_hp': self.max_hp,
            'status': self.get_current_status(game_state),
            'carrying': self.carrying,
            'prod_queue': self.production_queue,
            'prod_progress': self.production_progress,
            'radius': round(self.radius, 2),
            'width': self.width,
            'height': self.height,
            'waypoints': [{'x': round(wp.x, 2), 'y': round(wp.y, 2)} for wp in self.waypoints],
            'action_details': self.action.to_dict() if self.action else None
        }

    def set_action(self, action):
        """Changes the current action and clears pathfinding waypoints."""
        self.action = action
        self.waypoints = []

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.status = 'dead'
            self.action = None # Stop current behavior
            self.carrying = 0 # Drop minerals on death
            self.production_queue = [] # Cancel production

    def is_stuck_check(self):
        """Monitors progress and activates ghosting if trapped."""
        self.pos_memory.append(self.pos.copy())
        if len(self.pos_memory) > 30:
            self.pos_memory.pop(0)

        if len(self.pos_memory) == 30:
            from .actions import GatherAction
            is_mining = isinstance(self.action, GatherAction) and self.action.phase == 'mining'
            
            dist_moved = self.pos.dist_to(self.pos_memory[0])
            # If we haven't moved at least 0.5 tiles in 30 ticks, we are likely stuck
            if dist_moved < 0.5 and not is_mining:
                self.ghost_mode_ticks = 30
                self.pos_memory = []

    def move_towards(self, target_pos, game_state, ignore_static_id=None):
        """Moves the entity towards a target position with grid-aware collision and sliding."""
        # Backward compatibility: if no nav_grid, just move directly
        if not hasattr(game_state, 'nav_grid') or game_state.nav_grid is None:
            diff = target_pos - self.pos
            dist = diff.length()
            if dist > 0.01:
                move_dist = min(self.speed * game_state.tick_duration, dist)
                self.pos += diff.normalize() * move_dist
            return

        if self.ghost_mode_ticks > 0:
            self.ghost_mode_ticks -= 1
            diff = target_pos - self.pos
            dist = diff.length()
            if dist > 0.01:
                move_dist = min(self.speed * game_state.tick_duration, dist)
                self.pos += diff.normalize() * move_dist
            return

        self.is_stuck_check()

        diff = target_pos - self.pos
        dist = diff.length()
        if dist < 0.01:
            return

        direction = diff.normalize()
        
        # Probe ahead incrementally to prevent jumping over thin walls
        # Use a smaller step size and probe distance for precision
        step = min(0.05, self.speed * game_state.tick_duration / 2)
        probe_dist = self.speed * game_state.tick_duration * 2.0 # Probe 2 ticks ahead
        
        from .actions import GatherAction
        am_gathering = isinstance(self.action, GatherAction)
        # Gathering SCVs get a tiny bit of leniency to touch the edge properly
        eps = 0.05 if am_gathering else 0.2

        # If we are ALREADY blocked at current position, something is wrong
        if game_state.nav_grid.is_area_blocked(self.pos.x, self.pos.y, self.width, self.height, check_dynamic=False, entity=self, eps=eps):
            self.ghost_mode_ticks = 30

        check_dynamic = (not am_gathering) and (self.ghost_mode_ticks <= 0)
        current_eps = 0.4 if self.ghost_mode_ticks > 0 else eps
        
        is_blocked = False
        d = step
        while d <= probe_dist:
            check_pos = self.pos + direction * d
            if game_state.nav_grid.is_area_blocked(check_pos.x, check_pos.y, self.width, self.height, check_dynamic=check_dynamic, entity=self, eps=current_eps, ignore_static_id=ignore_static_id):
                is_blocked = True
                break
            d += step
            
        # ALWAYS check the exact move destination for safety
        move_dist = min(self.speed * game_state.tick_duration, dist)
        dest_pos = self.pos + direction * move_dist
        if not is_blocked and game_state.nav_grid.is_area_blocked(dest_pos.x, dest_pos.y, self.width, self.height, check_dynamic=check_dynamic, entity=self, eps=current_eps, ignore_static_id=ignore_static_id):
            is_blocked = True
        
        # If we're currently sliding, check if we've cleared the obstacle
        if self.slide_direction is not None:
            # Exit slide mode if the direct path is now clear
            if not is_blocked:
                self.slide_direction = None
                move_dist = min(self.speed * game_state.tick_duration, dist)
                self.pos += direction * move_dist
            else:
                self.slide_logic(target_pos, game_state, ignore_static_id=ignore_static_id)
        elif is_blocked:
            # First time hitting obstacle, enter slide mode
            self.slide_logic(target_pos, game_state, ignore_static_id=ignore_static_id)
        else:
            # No obstacle, move directly
            self.slide_direction = None
            move_dist = min(self.speed * game_state.tick_duration, dist)
            self.pos += direction * move_dist

    def slide_logic(self, target_pos, game_state, ignore_static_id=None):
        """Finds a tangent path around an obstacle and sticks to it.
        Uses a fan-sweep algorithm to smoothly follow walls and dive into gaps."""
        import math
        from .utils import Vector2D
        from .actions import GatherAction
        am_gathering = isinstance(self.action, GatherAction)
        
        orig_diff = target_pos - self.pos
        orig_dir = orig_diff.normalize()
        
        def get_clearance(test_dir, max_d=3.5):
            step = 0.1 # Finer steps for sliding
            d = step
            last_safe = 0
            # Gathering SCVs get a tiny bit of leniency to touch the edge properly
            eps = 0.05 if am_gathering else 0.2
            while d <= max_d:
                p = self.pos + test_dir * d
                if game_state.nav_grid.is_area_blocked(p.x, p.y, self.width, self.height, check_dynamic=not am_gathering, entity=self, eps=eps, ignore_static_id=ignore_static_id):
                    break
                last_safe = d
                d += step
            return last_safe

        # If no direction chosen, pick the one with the best immediate opening
        if self.slide_direction is None:
            best_left_clear = -1
            best_left_angle = 180
            for angle in range(0, 181, 15):
                rad = math.radians(angle)
                test_dir = Vector2D(
                    orig_dir.x * math.cos(rad) - orig_dir.y * math.sin(rad),
                    orig_dir.x * math.sin(rad) + orig_dir.y * math.cos(rad)
                )
                c = get_clearance(test_dir)
                if c > best_left_clear:
                    best_left_clear = c
                    best_left_angle = angle
                    
            best_right_clear = -1
            best_right_angle = 180
            for angle in range(0, 181, 15):
                rad = math.radians(-angle)
                test_dir = Vector2D(
                    orig_dir.x * math.cos(rad) - orig_dir.y * math.sin(rad),
                    orig_dir.x * math.sin(rad) + orig_dir.y * math.cos(rad)
                )
                c = get_clearance(test_dir)
                if c > best_right_clear:
                    best_right_clear = c
                    best_right_angle = angle
                    
            if best_left_clear > best_right_clear:
                self.slide_direction = 'left'
            elif best_right_clear > best_left_clear:
                self.slide_direction = 'right'
            elif best_left_angle <= best_right_angle:
                self.slide_direction = 'left'
            else:
                self.slide_direction = 'right'

        # Now sweep in the chosen direction
        angles_to_test = range(0, 181, 15)
        
        best_dir = None
        best_clearance = -1
        best_angle = 180
        
        for angle in angles_to_test:
            rad = math.radians(angle if self.slide_direction == 'left' else -angle)
            test_dir = Vector2D(
                orig_dir.x * math.cos(rad) - orig_dir.y * math.sin(rad),
                orig_dir.x * math.sin(rad) + orig_dir.y * math.cos(rad)
            )
            c = get_clearance(test_dir)
            if c > best_clearance:
                best_clearance = c
                best_dir = test_dir
                best_angle = angle
                
        if best_clearance <= 0:
            # Completely blocked this way, switch!
            self.slide_direction = 'right' if self.slide_direction == 'left' else 'left'
            return # Move next tick
            
        move_dist = min(self.speed * game_state.tick_duration, orig_diff.length())
            
        if best_angle == 0 and best_clearance >= move_dist:
            self.slide_direction = None # We are clear!
            
        # Move
        move_dist = min(move_dist, best_clearance)
        self.pos += best_dir * move_dist

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
        
        # Handle production if this is a producer
        if self.production_queue:
            self._handle_production(game_state)

        # Soft Collision (Repulsion)
        if self.type not in ['base', 'mineral_patch']:
            self._apply_repulsion(game_state)

        # Boundary clamping: keep units inside the map
        if hasattr(game_state, 'map_data'):
            self.pos.x = max(0, min(self.pos.x, game_state.map_data.width))
            self.pos.y = max(0, min(self.pos.y, game_state.map_data.height))

    def _apply_repulsion(self, game_state):
        """Pushes away from nearby units to prevent overlapping based on rectangular dimensions"""
        if not hasattr(game_state, 'grid'):
            return
            
        from .actions import GatherAction
        # SCV GHOSTING: Gathering units ignore repulsion to prevent gridlocks at minerals/bases
        if isinstance(self.action, GatherAction):
            return

        nearby_ids = game_state.grid.get_nearby_ids(self.pos)
        from .utils import rect_dist, Vector2D
        import random
        
        for eid in nearby_ids:
            if eid == self.id: continue
            other = game_state.entities.get(eid)
            if not other or other.status == 'dead' or other.definition.get('category') in ['building', 'resource']:
                continue
            
            # If the OTHER unit is gathering, we also ignore it to let it pass
            if isinstance(other.action, GatherAction):
                continue

            dist = rect_dist(self.pos, self.width, self.height, other.pos, other.width, other.height)
            if dist <= 0: # Overlapping
                # Repel with a force proportional to tick duration to avoid "variable speed" jumps
                overlap_depth = 0.05 * game_state.tick_duration
                push_dir = (self.pos - other.pos).normalize()
                if push_dir.length_sq() < 0.01:
                    push_dir = Vector2D(random.uniform(-1,1), random.uniform(-1,1)).normalize()
                self.pos += push_dir * overlap_depth


    def _handle_production(self, game_state):
        unit_type = self.production_queue[0]
        stats = UNIT_DEFINITIONS.get(unit_type)
        build_time = stats.get('build_time', 100)
        
        self.production_progress += 1
        
        if self.production_progress >= build_time:
            # Spawn unit just outside the building's radius
            # We use a slight offset of 1.0 beyond the radius
            spawn_dist = self.radius + stats.get('radius', 1.0) + 1.0
            new_unit = Entity(unit_type, self.owner_id, self.pos.x, self.pos.y + spawn_dist)
            game_state.add_entity(new_unit)
            
            # Clean up queue
            self.production_queue.pop(0)
            self.production_progress = 0


class ProductionAI:
    """Manages simple automated production for a player"""
    def __init__(self, player_id):
        self.player_id = player_id

    def update(self, simulator):
        # 1. Production
        if simulator.resources[self.player_id] >= 50:
            simulator.request_unit(self.player_id, 'scv')
            
        # 2. Maintenance: Re-assign idle scvs
        from .actions import GatherAction
        for ent in simulator.entities.values():
            if ent.owner_id == self.player_id and ent.type == 'scv' and ent.status != 'dead':
                if ent.action is None:
                    # Find a job (locally)
                    patch_id = GatherAction(None)._find_best_patch(ent, simulator, max_dist=30.0)
                    if patch_id:
                        ent.set_action(GatherAction(patch_id))
                        ent.action.prepare(ent, simulator)

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
            # Default map
            self.map_data = Map(
                width=128, 
                height=128, 
                spawn_points={'p1': Vector2D(10, 10), 'p2': Vector2D(118, 118)},
                minerals=[]
            )

        self.max_ticks = max_ticks
        self.entities = {} # Use dict for fast lookup by ID
        self.grid = SpatialGrid(self.map_data.width, self.map_data.height)
        self.nav_grid = NavigationGrid(self.map_data.width, self.map_data.height)
        self.pathfinder = AStarPathfinder(self.nav_grid)
        self.history = [] # Stores deltas
        self.resources = {
            self.player1_id: 50.0,
            self.player2_id: 50.0
        }
        self.ai_controllers = [
            ProductionAI(self.player1_id),
            ProductionAI(self.player2_id)
        ]
        self.triggers = {}  # tick -> list of {'entity_id': str, 'action': Action}
        self.tick_duration = 0.1 # Standard simulation step (10 ticks per second)

    def add_minerals(self, player_id, amount):
        if player_id in self.resources:
            self.resources[player_id] += amount

    def request_unit(self, player_id, unit_type):
        """Attempts to queue a unit for production"""
        stats = UNIT_DEFINITIONS.get(unit_type)
        if not stats or self.resources[player_id] < stats.get('cost', {}).get('minerals', 0):
            return False
            
        # Find an appropriate production building (just 'base' for now)
        bases = [e for e in self.entities.values() 
                 if e.owner_id == player_id and e.type == 'base' and e.status != 'dead']
        
        if not bases:
            return False
            
        # Add to the base with the shortest queue
        best_base = min(bases, key=lambda b: len(b.production_queue))
        
        if len(best_base.production_queue) < 5: # Max queue length
            self.resources[player_id] -= stats.get('cost', {}).get('minerals', 0)
            best_base.production_queue.append(unit_type)
            return True
            
        return False

    def add_entity(self, entity):
        self.entities[entity.id] = entity
        
        # Update Nav Grid for buildings/minerals
        if entity.definition.get('category') in ['building', 'resource']:
            self.nav_grid.set_static_rect(entity.pos.x, entity.pos.y, entity.width, entity.height, entity.id)

    def setup_match(self):
        # 1. Minerals FIRST so scvs can find them when spawned
        for m in self.map_data.minerals:
            if hasattr(m, 'x'):
                mx, my = m.x, m.y
            else:
                mx, my = m['x'], m['y']
            patch = Entity('mineral_patch', 'neutral', mx, my)
            patch.pos.x += patch.width / 2.0
            patch.pos.y += patch.height / 2.0
            self.add_entity(patch)

        # Load mineral patches from YAML entities list
        for ent_config in self.map_data.entities:
            if ent_config.get('type') != 'mineral_patch':
                continue
            patch = Entity(
                'mineral_patch',
                ent_config.get('owner', 'neutral'),
                ent_config.get('x', 0),
                ent_config.get('y', 0),
                entity_id=ent_config.get('id')
            )
            patch.pos.x += patch.width / 2.0
            patch.pos.y += patch.height / 2.0
            self.add_entity(patch)

        # 2. Spawns (Bases)
        spawns = self.map_data.spawn_points
        for pid, pos in spawns.items():
            if hasattr(pos, 'x'):
                px, py = pos.x, pos.y
            else:
                px, py = pos['x'], pos['y']
            base = Entity('base', pid, px, py)
            base.pos.x += base.width / 2.0
            base.pos.y += base.height / 2.0
            self.add_entity(base)
            
            # 3. Initial scvs near base (spawned AFTER minerals)
            bx, by = base.pos.x, base.pos.y
            offsets = [(-1.5, 2.5), (-0.5, 2.5), (0.5, 2.5), (1.5, 2.5)] 
            for i in range(4):
                ox, oy = offsets[i]
                self.add_entity(Entity('scv', pid, bx + ox, by + oy))



    def simulate(self):
        """Runs the simulation and returns delta-based JSON history.
        
        Entities must be set up before calling this method.
        For a normal match, call setup_match() first.
        For scenarios, add entities manually and configure triggers.
        """
        # Ensure all entities have correct HP before first snapshot
        for e in self.entities.values():
            if e.hp <= 0 and e.status != 'dead':
                e.hp = e.definition.get('hp', 100)
                e.max_hp = e.definition.get('max_hp', e.hp)

        # 1. Execute initial triggers (Tick 0) BEFORE capturing state
        # This ensures Tick 0 status reflects the starting orders
        for trigger in self.triggers.get(0, []):
            entity = self.entities.get(trigger['entity_id'])
            if entity:
                entity.set_action(trigger['action'])
                entity.action.prepare(entity, self)

        # 2. Initial State (Tick 0 Snapshot)
        initial_state = [e.to_dict(self) for e in self.entities.values()]
        self.history.append({
            'tick': 0, 
            'map': {'width': self.map_data.width, 'height': self.map_data.height},
            'entities': initial_state,
            'resources': self.resources.copy()
        })

        # 1. Main Simulation Loop
        for tick in range(1, self.max_ticks + 1):
            # 1. Capture Snapshots BEFORE triggers and updates
            pre_update_snapshots = {eid: ent.to_dict(self) for eid, ent in self.entities.items()}
            old_resources = self.resources.copy()
            old_entity_ids = set(self.entities.keys())

            # 2. Execute triggers for this tick
            for trigger in self.triggers.get(tick, []):
                entity = self.entities.get(trigger['entity_id'])
                if entity:
                    entity.set_action(trigger['action'])
                    entity.action.prepare(entity, self)

            # 3. Update Controllers
            for ai in self.ai_controllers:
                ai.update(self)
            
            # 4. Prepare Spatial Search & Nav Grid
            self.grid.clear()
            self.nav_grid.clear_dynamic()
            for ent in self.entities.values():
                if ent.status != 'dead':
                    self.grid.insert(ent)
                    if ent.definition.get('category') == 'unit':
                        self.nav_grid.set_dynamic_rect(ent.pos.x, ent.pos.y, ent.width, ent.height, ent.id)
            
            # 5. Physics/Behavior Update
            for ent in list(self.entities.values()):
                ent.update(self)

            # 6. Record Deltas
            tick_deltas = []
            for ent_id, ent in self.entities.items():
                if ent_id not in old_entity_ids:
                    # New entity spawned
                    tick_deltas.append(ent.to_dict(self))
                else:
                    # Existing entity - calculate delta
                    old_snapshot = pre_update_snapshots[ent_id]
                    new_snapshot = ent.to_dict(self)
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
