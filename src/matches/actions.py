"""
Action system for unit behaviors.
Each action class represents a command button in StarCraft.
"""
from abc import ABC, abstractmethod


class Action(ABC):
    """Base class for all unit actions"""
    
    @abstractmethod
    def update(self, entity, game_state):
        """Execute one tick of this action"""
        pass
    
    @abstractmethod
    def get_status(self):
        """Return the status string for visualization"""
        pass


class GatherAction(Action):
    """Gather minerals from a mineral patch (Gather button)"""
    
    def __init__(self, target_patch_id):
        self.target_patch_id = target_patch_id
        self.phase = 'moving_to_patch'  # or 'mining' or 'returning'
        self.mining_cooldown = 0
    
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
            self.target_patch_id = self._find_nearest_unoccupied_patch(entity, game_state)
            if not self.target_patch_id:
                # No patches available
                entity.action = None
                return
            patch = game_state.entities.get(self.target_patch_id)
        
        # Check if patch is occupied by another worker
        if patch.occupied_by and patch.occupied_by != entity.id:
            # Patch is occupied - find another
            self.target_patch_id = self._find_nearest_unoccupied_patch(entity, game_state)
            if not self.target_patch_id:
                # No unoccupied patches - wait/idle
                entity.action = None
                return
            patch = game_state.entities.get(self.target_patch_id)
        
        # Move towards patch
        diff = patch.pos - entity.pos
        dist = diff.length()
        
        # Adjust distance for radii (edge-to-edge)
        actual_dist = max(0, dist - entity.radius - patch.radius)
        
        if actual_dist <= entity.range:
            # Arrived at patch - claim it and start mining
            patch.occupied_by = entity.id
            self.phase = 'mining'
            # Ensure at least 1 tick of mining to prevent instant pickup
            self.mining_cooldown = max(1, entity.harvest_time)
        else:
            # Keep moving
            move_dist = min(entity.speed, dist - entity.range + 0.1)
            entity.pos += diff.normalize() * move_dist
    
    def _mine(self, entity, game_state):
        # Wait for mining to complete
        if self.mining_cooldown > 0:
            self.mining_cooldown -= 1
            return
        
        # Mining complete - pick up minerals and release patch
        patch = game_state.entities.get(self.target_patch_id)
        if patch and patch.hp > 0:
            patch.hp -= entity.harvest_amount
            entity.carrying = entity.harvest_amount
            entity.last_patch_id = patch.id
            # Release the patch for other workers
            patch.occupied_by = None
        
        self.phase = 'returning'
    
    def _return_to_base(self, entity, game_state):
        # Find nearest base
        bases = [e for e in game_state.entities.values()
                if e.owner_id == entity.owner_id and e.type == 'base' and e.status != 'dead']
        
        if not bases:
            # No base - stop gathering
            entity.action = None
            entity.carrying = 0
            return
        
        closest_base = min(bases, key=lambda b: entity.pos.dist_to_sq(b.pos))
        
        # Move towards base
        diff = closest_base.pos - entity.pos
        dist = diff.length()
        
        # Adjust distance for radii (edge-to-edge)
        actual_dist = max(0, dist - entity.radius - closest_base.radius)
        
        if actual_dist <= entity.range:
            # Arrived - deposit minerals instantly
            game_state.add_minerals(entity.owner_id, entity.carrying)
            entity.carrying = 0
            self.phase = 'moving_to_patch'
        else:
            # Keep moving
            move_dist = min(entity.speed, dist - entity.range + 0.1)
            entity.pos += diff.normalize() * move_dist
    
    def _find_nearest_patch(self, entity, game_state):
        """Find the nearest mineral patch with resources"""
        patches = [e for e in game_state.entities.values()
                  if e.type == 'mineral_patch' and e.hp > 0]
        if not patches:
            return None
        nearest = min(patches, key=lambda p: entity.pos.dist_to_sq(p.pos))
        return nearest.id
    
    def _find_nearest_unoccupied_patch(self, entity, game_state):
        """Find the nearest unoccupied mineral patch with resources"""
        patches = [e for e in game_state.entities.values()
                  if e.type == 'mineral_patch' and e.hp > 0 
                  and (e.occupied_by is None or e.occupied_by == entity.id)]
        if not patches:
            return None
        nearest = min(patches, key=lambda p: entity.pos.dist_to_sq(p.pos))
        return nearest.id
    
    def get_status(self):
        if self.phase == 'moving_to_patch':
            return 'harvest'
        elif self.phase == 'mining':
            return 'mining'
        elif self.phase == 'returning':
            return 'return'


class AttackAction(Action):
    """Attack a target unit (Attack button)"""
    
    def __init__(self, target_id):
        self.target_id = target_id
    
    def update(self, entity, game_state):
        target = game_state.entities.get(self.target_id)
        
        # Target dead or missing - stop attacking
        if not target or target.status == 'dead':
            entity.action = None
            return
        
        diff = target.pos - entity.pos
        dist = diff.length()
        
        # Adjust distance for radii (edge-to-edge)
        actual_dist = max(0, dist - entity.radius - target.radius)
        
        if actual_dist <= entity.range:
            # In range - attack if cooldown ready
            if entity.current_cooldown <= 0:
                target.take_damage(entity.damage)
                entity.current_cooldown = entity.cooldown
        else:
            # Move into range
            move_dist = min(entity.speed, dist - entity.range + 0.1)
            entity.pos += diff.normalize() * move_dist
    
    def get_status(self):
        return 'attack'


class MoveAction(Action):
    """Move to a destination (Move button)"""
    
    def __init__(self, destination):
        self.destination = destination
    
    def update(self, entity, game_state):
        diff = self.destination - entity.pos
        dist = diff.length()
        
        if dist < 0.5:
            # Arrived
            entity.action = None
        else:
            # Keep moving
            move_dist = min(entity.speed, dist)
            entity.pos += diff.normalize() * move_dist
    
    def get_status(self):
        return 'move'


class HoldAction(Action):
    """Hold position and attack nearby enemies (Hold button)"""
    
    def update(self, entity, game_state):
        # Don't move, but attack nearby enemies
        enemies = [e for e in game_state.entities.values()
                  if e.owner_id != entity.owner_id and e.status != 'dead'
                  and e.type not in ['mineral_patch', 'base']]
        
        if not enemies:
            return
        
        # Find closest enemy in range
        in_range = [e for e in enemies 
                   if entity.pos.dist_to(e.pos) <= entity.range]
        
        if in_range:
            target = min(in_range, key=lambda e: entity.pos.dist_to_sq(e.pos))
            if entity.current_cooldown <= 0:
                target.take_damage(entity.damage)
                entity.current_cooldown = entity.cooldown
    
    def get_status(self):
        return 'idle'  # Hold position shows as idle
