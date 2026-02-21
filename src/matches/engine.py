import uuid
import random
import json
import math
from .data import UNIT_STATS
from .utils import Vector2D
from .actions import GatherAction, AttackAction, MoveAction, HoldAction

class Map:
    """Stores static map data: dimensions, spawns, and terrain."""
    def __init__(self, name="Default", width=128, height=128, spawn_points=None, minerals=None):
        self.name = name
        self.width = width
        self.height = height
        # Default spawns if none provided
        self.spawn_points = spawn_points or {
            'p1': Vector2D(10, 10),
            'p2': Vector2D(width - 10, height - 10)
        }
        # List of {x, y} for mineral patches
        self.minerals = minerals or []
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
        x, y = int(pos.x), int(pos.y)
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return True # Edge of map
        
        # Static Layer
        if self.static_grid[x][y] and (not entity or self.static_grid[x][y] != entity.id):
            return True
        
        # Dynamic Layer
        if check_dynamic and self.dynamic_grid[x][y] and (not entity or self.dynamic_grid[x][y] != entity.id):
            return True
        return False

    def clear_dynamic(self):
        for x in range(self.width):
            for y in range(self.height):
                self.dynamic_grid[x][y] = None

    def set_static(self, x, y, entity_id):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.static_grid[int(x)][int(y)] = entity_id

    def set_dynamic(self, x, y, entity_id):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.dynamic_grid[int(x)][int(y)] = entity_id

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
        
        # Collision & Navigation
        self.pos_memory = []
        self.ghost_mode_ticks = 0
        self.slide_direction = None # None, 'left', or 'right'
        self.last_slide_normal = None

    def get_current_status(self, game_state=None):
        """Returns the status string from the current action or default"""
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

    def to_dict(self, game_state=None):
        return {
            'id': self.id,
            'type': self.type,
            'owner_id': self.owner_id,
            'x': round(self.pos.x, 2),
            'y': round(self.pos.y, 2),
            'hp': round(self.hp, 2),
            'status': self.get_current_status(game_state),
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

    def is_stuck_check(self):
        """Monitors progress and activates ghosting if trapped."""
        self.pos_memory.append(self.pos.copy())
        if len(self.pos_memory) > 100:
            self.pos_memory.pop(0)

        if len(self.pos_memory) == 100:
            from .actions import GatherAction
            is_mining = isinstance(self.action, GatherAction) and self.action.phase == 'mining'
            
            dist_moved = self.pos.dist_to(self.pos_memory[0])
            # High threshold (10.0) to ensure units trapped in small enclosures (like minerals) trigger it
            if dist_moved < 10.0 and not is_mining:
                # STUCK! Activate ghosting
                self.ghost_mode_ticks = 20
                self.pos_memory = [] # Reset memory

    def move_towards(self, target_pos, game_state):
        """Moves the entity towards a target position with grid-aware collision and sliding."""
        # Backward compatibility: if no nav_grid, just move directly
        if not hasattr(game_state, 'nav_grid') or game_state.nav_grid is None:
            diff = target_pos - self.pos
            dist = diff.length()
            if dist > 0.01:
                move_dist = min(self.speed, dist)
                self.pos += diff.normalize() * move_dist
            return

        if self.ghost_mode_ticks > 0:
            self.ghost_mode_ticks -= 1
            diff = target_pos - self.pos
            dist = diff.length()
            if dist > 0.01:
                move_dist = min(self.speed, dist)
                self.pos += diff.normalize() * move_dist
            return

        self.is_stuck_check()

        diff = target_pos - self.pos
        dist = diff.length()
        if dist < 0.01:
            return

        direction = diff.normalize()
        
        # Probe ahead (at least speed distance)
        probe_dist = max(1.0, self.speed)
        probe_pos = self.pos + direction * probe_dist
        
        from .actions import GatherAction
        am_gathering = isinstance(self.action, GatherAction)
        
        # Check Layer A (Static) and Layer B (Dynamic - if not gathering)
        is_blocked = game_state.nav_grid.is_blocked(probe_pos, check_dynamic=not am_gathering, entity=self)
        
        # If we're currently sliding, check if we've cleared the obstacle
        if self.slide_direction is not None:
            # Exit slide mode if the direct path is now clear
            if not is_blocked:
                self.slide_direction = None
                move_dist = min(self.speed, dist)
                self.pos += direction * move_dist
            else:
                # Still blocked, try gap detection first
                gap_pos = self.find_gap(target_pos, game_state)
                if gap_pos is not None:
                    # Head toward the gap
                    gap_dir = gap_pos - self.pos
                    if gap_dir.length() > 0.1:
                        move_dir = gap_dir.normalize()
                        move_dist = min(self.speed, gap_dir.length())
                        # Verify the move is safe
                        test_pos = self.pos + move_dir * move_dist
                        if not game_state.nav_grid.is_blocked(test_pos, check_dynamic=not am_gathering, entity=self):
                            self.pos += move_dir * move_dist
                            self.slide_direction = None
                            return
                # No gap or gap unreachable, keep sliding
                self.slide_logic(target_pos, game_state)
        elif is_blocked:
            # First time hitting obstacle, try gap detection first
            gap_pos = self.find_gap(target_pos, game_state)
            if gap_pos is not None:
                # Head toward the gap
                gap_dir = gap_pos - self.pos
                if gap_dir.length() > 0.1:
                    move_dir = gap_dir.normalize()
                    move_dist = min(self.speed, gap_dir.length())
                    # Verify the move is safe
                    test_pos = self.pos + move_dir * move_dist
                    if not game_state.nav_grid.is_blocked(test_pos, check_dynamic=not am_gathering, entity=self):
                        self.pos += move_dir * move_dist
                        return
            # No gap found, enter slide mode
            self.slide_logic(target_pos, game_state)
        else:
            # No obstacle, move directly
            self.slide_direction = None
            move_dist = min(self.speed, dist)
            self.pos += direction * move_dist

    def find_gap(self, target_pos, game_state):
        """Find first opening (gap) in the obstacle in direction of target.
        Looks for navigable tiles that come right after blocked tiles."""
        from .actions import GatherAction
        am_gathering = isinstance(self.action, GatherAction)
        
        # 1. Buscar en rayo directo hacia el objetivo
        gap = self._scan_ray(target_pos, game_state, am_gathering)
        if gap:
            return gap
        
        # 2. Buscar gaps horizontales: tiles navegables que están después de tiles bloqueados
        # Buscar hacia la derecha
        for dx in range(1, 15):
            for dy in range(-10, 11):
                check_pos = Vector2D(self.pos.x + dx, self.pos.y + dy)
                
                # Este tile debe ser navegable
                if game_state.nav_grid.is_blocked(check_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                # El tile inmediatamente a la izquierda debe ser BLOQUEADO
                prev_pos = Vector2D(self.pos.x + dx - 1, self.pos.y + dy)
                if not game_state.nav_grid.is_blocked(prev_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                # Este es un gap horizontal! Verificar que acerca al objetivo
                if check_pos.dist_to(target_pos) < self.pos.dist_to(target_pos):
                    return check_pos
        
        # Buscar hacia la izquierda
        for dx in range(1, 15):
            for dy in range(-10, 11):
                check_pos = Vector2D(self.pos.x - dx, self.pos.y + dy)
                
                if game_state.nav_grid.is_blocked(check_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                prev_pos = Vector2D(self.pos.x - dx + 1, self.pos.y + dy)
                if not game_state.nav_grid.is_blocked(prev_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                if check_pos.dist_to(target_pos) < self.pos.dist_to(target_pos):
                    return check_pos
        
        # Buscar gaps verticales
        # Buscar hacia abajo
        for dy in range(1, 15):
            for dx in range(-10, 11):
                check_pos = Vector2D(self.pos.x + dx, self.pos.y + dy)
                
                if game_state.nav_grid.is_blocked(check_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                prev_pos = Vector2D(self.pos.x + dx, self.pos.y + dy - 1)
                if not game_state.nav_grid.is_blocked(prev_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                if check_pos.dist_to(target_pos) < self.pos.dist_to(target_pos):
                    return check_pos
        
        # Buscar hacia arriba
        for dy in range(1, 15):
            for dx in range(-10, 11):
                check_pos = Vector2D(self.pos.x + dx, self.pos.y - dy)
                
                if game_state.nav_grid.is_blocked(check_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                prev_pos = Vector2D(self.pos.x + dx, self.pos.y - dy + 1)
                if not game_state.nav_grid.is_blocked(prev_pos, check_dynamic=not am_gathering, entity=self):
                    continue
                
                if check_pos.dist_to(target_pos) < self.pos.dist_to(target_pos):
                    return check_pos
        
        return None

    def _scan_ray(self, target_pos, game_state, am_gathering):
        """Escanea desde posición actual hacia objetivo, retorna primer gap."""
        direction = (target_pos - self.pos).normalize()
        
        for dist in range(1, 15):
            check_pos = self.pos + direction * dist
            
            if not game_state.nav_grid.is_blocked(check_pos, check_dynamic=not am_gathering, entity=self):
                return check_pos
        
        return None

    def _scan_ray(self, target_pos, game_state, am_gathering):
        """Escanea desde posición actual hacia objetivo, retorna primer gap."""
        direction = (target_pos - self.pos).normalize()
        
        for dist in range(1, 11):  # hasta 10 tiles ahead
            check_pos = self.pos + direction * dist
            
            if not game_state.nav_grid.is_blocked(check_pos, check_dynamic=not am_gathering, entity=self):
                return check_pos
        
        return None


    def slide_logic(self, target_pos, game_state):
        """Finds a tangent path around an obstacle and sticks to it."""
        from .actions import GatherAction
        am_gathering = isinstance(self.action, GatherAction)
        
        # Get original direction
        orig_diff = target_pos - self.pos
        orig_dir = orig_diff.normalize()
        
        # Try both tangents: Left and Right (90 degrees)
        tangent_left = Vector2D(-orig_dir.y, orig_dir.x)
        tangent_right = Vector2D(orig_dir.y, -orig_dir.x)
        
        def get_clearance(test_dir):
            """Measures how many units we can move in a direction before hitting something."""
            for step in range(1, 6): # Probe up to 5 units
                p = self.pos + test_dir * step
                if game_state.nav_grid.is_blocked(p, check_dynamic=not am_gathering, entity=self):
                    return step - 1
            return 10 # Path is relatively clear
            
        left_clear = get_clearance(tangent_left)
        right_clear = get_clearance(tangent_right)

        # Per-Tick Recovery: Stick to the chosen side but verify every tick.
        # Switch only if the other side becomes significantly (>50%) better to prevent jitter.
        if self.slide_direction is None:
            # First time hitting wall: Choose a side
            if left_clear == right_clear:
                # Tie-breaker: Choose the side that's more aligned with reaching the goal
                # Use dot product: higher value means more aligned
                # Since tangents are perpendicular to goal direction, we check which one
                # doesn't take us away from the goal
                left_dot = tangent_left.x * orig_dir.x + tangent_left.y * orig_dir.y
                right_dot = tangent_right.x * orig_dir.x + tangent_right.y * orig_dir.y
                
                # Choose the tangent with the higher (less negative) dot product
                # This picks the direction that's less perpendicular to the goal
                self.slide_direction = 'left' if left_dot >= right_dot else 'right'
            else:
                self.slide_direction = 'left' if left_clear >= right_clear else 'right'
        else:
            if self.slide_direction == 'left' and right_clear > left_clear * 1.5 and right_clear > 2:
                self.slide_direction = 'right'
            elif self.slide_direction == 'right' and left_clear > right_clear * 1.5 and left_clear > 2:
                self.slide_direction = 'left'
        
        # Move in chosen direction
        chosen_dir = tangent_left if self.slide_direction == 'left' else tangent_right
        
        # The Arc Cheat (Contour Following / Wall Hugging) / Rotation to find opening
        if game_state.nav_grid.is_blocked(self.pos + chosen_dir * 0.5, check_dynamic=not am_gathering, entity=self):
            found_path = False
            for angle_deg in [45, 135, 180]:
                rad = math.radians(angle_deg if self.slide_direction == 'left' else -angle_deg)
                test_dir = Vector2D(
                    orig_dir.x * math.cos(rad) - orig_dir.y * math.sin(rad),
                    orig_dir.x * math.sin(rad) + orig_dir.y * math.cos(rad)
                )
                if not game_state.nav_grid.is_blocked(self.pos + test_dir * 0.5, check_dynamic=not am_gathering, entity=self):
                    chosen_dir = test_dir
                    found_path = True
                    break
            
            if not found_path:
                self.slide_direction = 'right' if self.slide_direction == 'left' else 'left'
                chosen_dir = tangent_left if self.slide_direction == 'left' else tangent_right

        # Move along the wall - carefully probe to avoid jumping into walls
        move_dist = self.speed
        step = 0.1
        safe_dist = 0
        for d in range(1, int(move_dist / step) + 1):
            test_pos = self.pos + chosen_dir * (d * step)
            if game_state.nav_grid.is_blocked(test_pos, check_dynamic=not am_gathering, entity=self):
                break
            safe_dist = d * step
            
        if safe_dist > 0:
            self.pos += chosen_dir * safe_dist

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

    def _apply_repulsion(self, game_state):
        """Pushes away from nearby entities to prevent overlapping"""
        if not hasattr(game_state, 'grid'):
            return
            
        nearby_ids = game_state.grid.get_nearby_ids(self.pos)
        
        from .actions import GatherAction
        am_gathering = isinstance(self.action, GatherAction)
        
        my_radius = self.radius
        
        for other_id in nearby_ids:
            if other_id == self.id:
                continue
            other = game_state.entities.get(other_id)
            if not other or other.status == 'dead':
                continue
            
            # WORKER GHOSTING: 
            # Workers assigned to minerals ignore collision with buildings 
            # and other gathering workers to prevent gridlocks.
            if am_gathering:
                if other.type in ['base', 'mineral_patch']:
                    continue
                if other.type == 'worker' and isinstance(other.action, GatherAction):
                    continue
                
            # If both are buildings, they don't push each other
            if self.type in ['base', 'mineral_patch'] and other.type in ['base', 'mineral_patch']:
                continue

            diff = self.pos - other.pos
            dist_sq = diff.length_sq()
            min_dist = my_radius + other.radius
            
            if dist_sq < min_dist**2:
                # Push factor (softness)
                push_factor = 0.8 if other.type in ['base', 'mineral_patch', 'building'] else 0.2
                
                if dist_sq > 0.001:
                    dist = math.sqrt(dist_sq)
                    overlap = min_dist - dist
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
        # 1. Production
        if simulator.resources[self.player_id] >= 50:
            simulator.request_unit(self.player_id, 'worker')
            
        # 2. Maintenance: Re-assign idle workers
        from .actions import GatherAction
        for ent in simulator.entities.values():
            if ent.owner_id == self.player_id and ent.type == 'worker' and ent.status != 'dead':
                if ent.action is None:
                    # Find a job (locally)
                    patch_id = GatherAction(None)._find_best_patch(ent, simulator, max_dist=30.0)
                    if patch_id:
                        ent.action = GatherAction(patch_id)

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
        self.history = [] # Stores deltas
        self.resources = {
            self.player1_id: 50.0,
            self.player2_id: 50.0
        }
        self.grid = SpatialGrid(self.map_data.width, self.map_data.height)
        self.nav_grid = NavigationGrid(self.map_data.width, self.map_data.height)
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
        
        # Update Nav Grid for buildings/minerals
        if entity.type in ['base', 'mineral_patch']:
            bx, by = int(entity.pos.x - entity.width/2), int(entity.pos.y - entity.height/2)
            for ox in range(entity.width):
                for oy in range(entity.height):
                    self.nav_grid.set_static(bx + ox, by + oy, entity.id)

        # Assign default actions to newly spawned units
        from .actions import GatherAction, AttackAction
        if entity.type == 'worker':
            # Use smart distribution (even for initial/produced workers)
            # Use max_dist=50 for initial spawns to accommodate slightly spread layouts
            patch_id = GatherAction(None)._find_best_patch(entity, self, max_dist=50.0)
            if patch_id:
                entity.action = GatherAction(patch_id)
        
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
            # Support both dict {x, y} and Vector2D
            if hasattr(m, 'x'):
                mx, my = m.x, m.y
            else:
                mx, my = m['x'], m['y']
            patch = Entity('mineral_patch', 'neutral', mx, my)
            # Center it: (x, y) from editor is top-left
            patch.pos.x += patch.width / 2.0
            patch.pos.y += patch.height / 2.0
            self._spawn_entity(patch)

        # 2. Spawns (Bases)
        spawns = self.map_data.spawn_points
        for pid, pos in spawns.items():
            # Support both dict {x, y} and Vector2D
            if hasattr(pos, 'x'):
                px, py = pos.x, pos.y
            else:
                px, py = pos['x'], pos['y']
            base = Entity('base', pid, px, py)
            # Center it: (x, y) from editor is top-left
            base.pos.x += base.width / 2.0
            base.pos.y += base.height / 2.0
            self._spawn_entity(base)
            
            # 3. Initial workers near base (spawned AFTER minerals)
            # Spawn them in a row below the base
            bx, by = base.pos.x, base.pos.y
            offsets = [(-1.5, 2.5), (-0.5, 2.5), (0.5, 2.5), (1.5, 2.5)] 
            for i in range(4):
                ox, oy = offsets[i]
                self._spawn_entity(Entity('worker', pid, bx + ox, by + oy))

    def _add_entity(self, entity):
        self.entities[entity.id] = entity

    def simulate(self):
        """Runs the simulation and returns delta-based JSON history"""
        self._setup_initial_entities()
        
        # Initial State (Tick 0)
        initial_state = [e.to_dict(self) for e in self.entities.values()]
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
            # 2. Prepare Spatial Search & Nav Grid
            self.grid.clear()
            self.nav_grid.clear_dynamic()
            for ent in self.entities.values():
                if ent.status != 'dead':
                    self.grid.insert(ent)
                    if ent.type not in ['base', 'mineral_patch']:
                        self.nav_grid.set_dynamic(ent.pos.x, ent.pos.y, ent.id)
            
            # Clean up static grid for depleted minerals
            # (In a real engine we'd do this on death, but here we can refresh if needed)
            # Actually minerals don't move, so we only need to clear if they die.
            
            # 3. Capture Snapshots for delta calculation
            pre_update_snapshots = {eid: ent.to_dict(self) for eid, ent in self.entities.items()}
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
