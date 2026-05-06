"""
Action system for unit behaviors.
Each action class represents a command button in StarCraft.
"""
from abc import ABC, abstractmethod
import math
from .utils import rect_dist, get_nearest_point_on_rect


class Action(ABC):
    """Base class for all unit actions"""
    
    @abstractmethod
    def update(self, entity, game_state):
        """Execute one tick of this action"""
        pass

    def prepare(self, entity, game_state):
        """Initialize any state needed before the first update (e.g. pathfinding)"""
        pass
    
    @abstractmethod
    def get_status(self, entity=None, game_state=None):
        """Return the status string for visualization"""
        pass

    def to_dict(self):
        """Return internal state for debugging"""
        return {'type': self.__class__.__name__}


class GatherAction(Action):
    """Gather minerals from a mineral patch (Gather button)"""
    
    def __init__(self, target_patch_id):
        self.target_patch_id = target_patch_id
        self.phase = 'moving_to_patch'  # or 'mining' or 'returning'
        self.mining_cooldown = 0
    
    def to_dict(self):
        return {
            'type': 'GatherAction',
            'phase': self.phase,
            'target_id': self.target_patch_id,
            'cooldown': self.mining_cooldown
        }
    
    def update(self, entity, game_state):
        if self.phase == 'moving_to_patch':
            self._move_to_patch(entity, game_state)
        elif self.phase == 'mining':
            self._mine(entity, game_state)
        elif self.phase == 'returning':
            self._return_to_base(entity, game_state)
    
    def _move_to_patch(self, entity, game_state):
        patch = game_state.entities.get(self.target_patch_id)
        
        # Patch depleted or missing - find another
        if not patch or patch.hp <= 0:
            self.target_patch_id = self._find_best_patch(entity, game_state)
            if not self.target_patch_id:
                entity.action = None
                return
            patch = game_state.entities.get(self.target_patch_id)
        
        # Move towards patch
        actual_dist = rect_dist(entity.pos, entity.width, entity.height, patch.pos, patch.width, patch.height)
        
        dt = getattr(game_state, 'tick_duration', 0.1)
        arrival_threshold = entity.speed * dt * 1.5 
        
        if actual_dist <= entity.range + arrival_threshold:
            # Arrived at patch - check if we should stay or look for a free one
            if patch.occupied_by is None or patch.occupied_by == entity.id:
                # It's free! Claim it
                patch.occupied_by = entity.id
                self.phase = 'mining'
                self.mining_cooldown = max(1, entity.harvest_time)
                entity.waypoints = []
                return
            else:
                # It's occupied. Can we find a completely free one nearby?
                better_patch_id = self._find_best_patch(entity, game_state, only_unoccupied=True)
                if better_patch_id and better_patch_id != self.target_patch_id:
                    self.target_patch_id = better_patch_id
                else:
                    # Saturation: wait here
                    pass

        # Pathfinding for long distances
        if not entity.waypoints and entity.pos.dist_to(patch.pos) > 5.0:
            target_pos = get_nearest_point_on_rect(entity.pos, patch.pos, patch.width, patch.height)
            raw_path = game_state.pathfinder.find_path(entity.pos, target_pos, entity=entity, game_state=game_state)
            if raw_path:
                full_path = [entity.pos] + raw_path
                smoothed = game_state.pathfinder.smooth_path(full_path, entity, game_state)
                if len(smoothed) > 1:
                    smoothed.pop(0)
                entity.waypoints = smoothed

        if entity.waypoints:
            target = entity.waypoints[0]
            # Immunity setup
            ignore_ids = [patch.id]
            bases = [e for e in game_state.entities.values() if e.type == 'base' and e.owner_id == entity.owner_id]
            closest_base = min(bases, key=lambda b: entity.pos.dist_to_sq(b.pos)) if bases else None
            if closest_base and entity.pos.dist_to(closest_base.pos) < 5.0:
                ignore_ids.append(closest_base.id)

            ignore_cats = ['resource', 'building'] if actual_dist < 1.0 else None
            
            # Check for path obstruction if nav_grid is available
            nav_grid = getattr(game_state, 'nav_grid', None)
            if nav_grid and len(entity.waypoints) > 1 and nav_grid.is_area_blocked(target.x, target.y, entity.width, entity.height, check_dynamic=False, entity=entity, ignore_static_id=ignore_ids, ignore_categories=ignore_cats, game_state=game_state, eps=0.15):
                entity.waypoints = []
                return

            if entity.pos.dist_to(target) < arrival_threshold:
                entity.waypoints.pop(0)
                if entity.waypoints:
                    target = entity.waypoints[0]

            entity.move_towards(target, game_state, ignore_static_id=ignore_ids, ignore_categories=ignore_cats)
        else:
            target_pos = get_nearest_point_on_rect(entity.pos, patch.pos, patch.width, patch.height)
            ignore_ids = [patch.id]
            ignore_cats = ['resource', 'building'] if actual_dist < 1.0 else None
            entity.move_towards(target_pos, game_state, ignore_static_id=ignore_ids, ignore_categories=ignore_cats)
    
    def _mine(self, entity, game_state):
        patch = game_state.entities.get(self.target_patch_id)
        if not patch or patch.hp <= 0:
            self.phase = 'moving_to_patch'
            return

        if patch.occupied_by is not None and patch.occupied_by != entity.id:
            return
            
        if patch.occupied_by is None:
            patch.occupied_by = entity.id
            self.mining_cooldown = max(1, entity.harvest_time)

        if self.mining_cooldown > 0:
            self.mining_cooldown -= 1
            return
        
        patch.hp -= entity.harvest_amount
        entity.carrying = entity.harvest_amount
        entity.last_patch_id = patch.id
        patch.occupied_by = None
        self.phase = 'returning'
    
    def _return_to_base(self, entity, game_state):
        bases = [e for e in game_state.entities.values()
                if e.owner_id == entity.owner_id and e.type == 'base' and e.status != 'dead']
        
        if not bases:
            entity.action = None
            entity.carrying = 0
            return
        
        closest_base = min(bases, key=lambda b: entity.pos.dist_to_sq(b.pos))
        actual_dist = rect_dist(entity.pos, entity.width, entity.height, closest_base.pos, closest_base.width, closest_base.height)
        
        if actual_dist <= 0.1:
            game_state.add_minerals(entity.owner_id, entity.carrying)
            entity.carrying = 0
            self.phase = 'moving_to_patch'
            entity.waypoints = []
            return

        dt = getattr(game_state, 'tick_duration', 0.1)
        arrival_threshold = entity.speed * dt * 1.5 

        if not entity.waypoints and entity.pos.dist_to(closest_base.pos) > 5.0:
            target_pos = get_nearest_point_on_rect(entity.pos, closest_base.pos, closest_base.width, closest_base.height)
            raw_path = game_state.pathfinder.find_path(entity.pos, target_pos, entity=entity, game_state=game_state)
            if raw_path:
                full_path = [entity.pos] + raw_path
                smoothed = game_state.pathfinder.smooth_path(full_path, entity, game_state)
                if len(smoothed) > 1:
                    smoothed.pop(0)
                entity.waypoints = smoothed

        if entity.waypoints:
            target = entity.waypoints[0]
            ignore_ids = [closest_base.id]
            if entity.last_patch_id:
                ignore_ids.append(entity.last_patch_id)
            
            dist_to_patch = 999
            if entity.last_patch_id and entity.last_patch_id in game_state.entities:
                patch = game_state.entities[entity.last_patch_id]
                dist_to_patch = rect_dist(entity.pos, entity.width, entity.height, patch.pos, patch.width, patch.height)

            ignore_cats = ['resource', 'building'] if (actual_dist < 1.0 or dist_to_patch < 1.0) else None

            # Check for path obstruction if nav_grid is available
            nav_grid = getattr(game_state, 'nav_grid', None)
            if nav_grid and len(entity.waypoints) > 1 and nav_grid.is_area_blocked(target.x, target.y, entity.width, entity.height, check_dynamic=False, entity=entity, ignore_static_id=ignore_ids, ignore_categories=ignore_cats, game_state=game_state, eps=0.15):
                entity.waypoints = []
                return

            if entity.pos.dist_to(target) < arrival_threshold:
                entity.waypoints.pop(0)
                if entity.waypoints:
                    target = entity.waypoints[0]

            entity.move_towards(target, game_state, ignore_static_id=ignore_ids, ignore_categories=ignore_cats)
        else:
            target_pos = get_nearest_point_on_rect(entity.pos, closest_base.pos, closest_base.width, closest_base.height)
            ignore_ids = [closest_base.id]
            if entity.last_patch_id:
                ignore_ids.append(entity.last_patch_id)
            
            dist_to_patch = 999
            if entity.last_patch_id and entity.last_patch_id in game_state.entities:
                patch = game_state.entities[entity.last_patch_id]
                dist_to_patch = rect_dist(entity.pos, entity.width, entity.height, patch.pos, patch.width, patch.height)

            ignore_cats = ['resource', 'building'] if (actual_dist < 1.5 or dist_to_patch < 1.0) else None
            entity.move_towards(target_pos, game_state, ignore_static_id=ignore_ids, ignore_categories=ignore_cats)

    def _find_best_patch(self, entity, game_state, max_dist=30.0, only_unoccupied=False):
        patches = [e for e in game_state.entities.values() if e.type == 'mineral_patch' and e.hp > 0]
        if max_dist:
            patches = [p for p in patches if entity.pos.dist_to(p.pos) <= max_dist]
        if not patches:
            return None
        assigned_counts = {}
        for other in game_state.entities.values():
            if other.owner_id == entity.owner_id and other.type == 'scv' and isinstance(other.action, GatherAction):
                tid = other.action.target_patch_id
                assigned_counts[tid] = assigned_counts.get(tid, 0) + 1
        if only_unoccupied:
            unoccupied = [p for p in patches if p.occupied_by is None]
            if unoccupied:
                best = min(unoccupied, key=lambda p: entity.pos.dist_to_sq(p.pos))
                return best.id
            return None
        best = min(patches, key=lambda p: (assigned_counts.get(p.id, 0), entity.pos.dist_to_sq(p.pos)))
        return best.id
    
    def get_status(self, entity=None, game_state=None):
        if self.phase == 'moving_to_patch':
            return 'harvest'
        elif self.phase == 'mining':
            if game_state is not None:
                patch = game_state.entities.get(self.target_patch_id)
                if patch and patch.occupied_by is not None and patch.occupied_by != entity.id:
                    return 'waiting'
            return 'mining'
        elif self.phase == 'returning':
            return 'return'
        return 'gather'


class AttackAction(Action):
    def __init__(self, target_id):
        self.target_id = target_id
    def update(self, entity, game_state):
        target = game_state.entities.get(self.target_id)
        if not target or target.status == 'dead':
            entity.action = None
            return
        actual_dist = rect_dist(entity.pos, entity.width, entity.height, target.pos, target.width, target.height)
        if actual_dist <= entity.range:
            if entity.current_cooldown <= 0:
                target.take_damage(entity.damage)
                entity.current_cooldown = entity.cooldown
        else:
            if actual_dist > 5.0 and not entity.waypoints:
                raw_path = game_state.pathfinder.find_path(entity.pos, target.pos, entity=entity, game_state=game_state)
                if raw_path:
                    entity.waypoints = game_state.pathfinder.smooth_path(raw_path, entity, game_state)
            if entity.waypoints:
                wp = entity.waypoints[0]
                if entity.pos.dist_to(wp) < 0.5:
                    entity.waypoints.pop(0)
                    if entity.waypoints: wp = entity.waypoints[0]
                entity.move_towards(wp, game_state)
            else:
                target_pos = get_nearest_point_on_rect(entity.pos, target.pos, target.width, target.height)
                entity.move_towards(target_pos, game_state)
    def get_status(self, entity=None, game_state=None): return 'attack'


class MoveAction(Action):
    def __init__(self, destination):
        self.destination = destination
    def update(self, entity, game_state):
        if not entity.waypoints:
            raw_path = game_state.pathfinder.find_path(entity.pos, self.destination, entity=entity, game_state=game_state)
            if raw_path:
                entity.waypoints = game_state.pathfinder.smooth_path(raw_path, entity, game_state)
            else:
                entity.waypoints = [self.destination]
        target = entity.waypoints[0]
        dt = getattr(game_state, 'tick_duration', 0.1)
        arrival_threshold = entity.speed * dt * 1.1
        if entity.pos.dist_to(target) < arrival_threshold:
            entity.waypoints.pop(0)
            if not entity.waypoints:
                entity.action = None
                return
            target = entity.waypoints[0]
        entity.move_towards(target, game_state)
    def get_status(self, entity=None, game_state=None): return 'move'


class HoldAction(Action):
    def update(self, entity, game_state):
        enemies = [e for e in game_state.entities.values() if e.owner_id != entity.owner_id and e.status != 'dead' and e.type not in ['mineral_patch', 'base']]
        if not enemies: return
        in_range = [e for e in enemies if entity.pos.dist_to(e.pos) <= entity.range]
        if in_range:
            target = min(in_range, key=lambda e: entity.pos.dist_to_sq(e.pos))
            if entity.current_cooldown <= 0:
                target.take_damage(entity.damage)
                entity.current_cooldown = entity.cooldown
    def get_status(self, entity=None, game_state=None): return 'hold'
