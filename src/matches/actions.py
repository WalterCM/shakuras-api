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
            self.target_patch_id = self._find_best_patch(entity, game_state)
            if not self.target_patch_id:
                entity.action = None
                return
            patch = game_state.entities.get(self.target_patch_id)
        
        # Move towards patch
        diff = patch.pos - entity.pos
        dist = diff.length()
        actual_dist = max(0, dist - entity.radius - patch.radius)
        
        if actual_dist <= entity.range:
            # Arrived at patch - check if we should stay or look for a free one
            if patch.occupied_by is None or patch.occupied_by == entity.id:
                # It's free! Claim it
                patch.occupied_by = entity.id
                self.phase = 'mining'
                self.mining_cooldown = max(1, entity.harvest_time)
            else:
                # It's occupied. Can we find a completely free one nearby?
                # This mirrors the "it checks the status only after reaching it" logic
                better_patch_id = self._find_best_patch(entity, game_state, only_unoccupied=True)
                if better_patch_id and better_patch_id != self.target_patch_id:
                    self.target_patch_id = better_patch_id
                    # We don't start mining immediately, we have to travel to the new one
                else:
                    # No free ones nearby? Just wait here (Saturation)
                    self.phase = 'mining'
        else:
            # Keep moving
            entity.move_towards(patch.pos, game_state)
    
    def _mine(self, entity, game_state):
        patch = game_state.entities.get(self.target_patch_id)
        if not patch or patch.hp <= 0:
            self.phase = 'moving_to_patch'
            return

        # Check if we can start/continue mining
        if patch.occupied_by is not None and patch.occupied_by != entity.id:
            # Someone else is mining - wait
            return
            
        # Claim it if we were waiting
        if patch.occupied_by is None:
            patch.occupied_by = entity.id
            self.mining_cooldown = max(1, entity.harvest_time)

        # Wait for mining to complete
        if self.mining_cooldown > 0:
            self.mining_cooldown -= 1
            return
        
        # Mining complete - pick up minerals and release patch
        patch.hp -= entity.harvest_amount
        entity.carrying = entity.harvest_amount
        entity.last_patch_id = patch.id
        patch.occupied_by = None
        self.phase = 'returning'
    
    def _return_to_base(self, entity, game_state):
        # Find nearest base
        bases = [e for e in game_state.entities.values()
                if e.owner_id == entity.owner_id and e.type == 'base' and e.status != 'dead']
        
        if not bases:
            entity.action = None
            entity.carrying = 0
            return
        
        closest_base = min(bases, key=lambda b: entity.pos.dist_to_sq(b.pos))
        
        # Move towards base
        diff = closest_base.pos - entity.pos
        dist = diff.length()
        actual_dist = max(0, dist - entity.radius - closest_base.radius)
        
        if actual_dist <= entity.range:
            # Arrived - deposit minerals
            game_state.add_minerals(entity.owner_id, entity.carrying)
            entity.carrying = 0
            self.phase = 'moving_to_patch'
            # Persistence: We no longer re-assign here. 
            # We stick to our target_patch_id until we arrive and see it's blocked.
        else:
            # Keep moving
            entity.move_towards(closest_base.pos, game_state)
    def _find_best_patch(self, entity, game_state, max_dist=30.0, only_unoccupied=False):
        """Find the best mineral patch considering distance and current worker assignments"""
        patches = [e for e in game_state.entities.values()
                  if e.type == 'mineral_patch' and e.hp > 0]
        
        # Locality: Filter by distance
        if max_dist:
            patches = [p for p in patches if entity.pos.dist_to(p.pos) <= max_dist]
            
        if not patches:
            return None
            
        # Count current assignments
        assigned_counts = {}
        for other in game_state.entities.values():
            if other.owner_id == entity.owner_id and other.type == 'worker' and isinstance(other.action, GatherAction):
                tid = other.action.target_patch_id
                assigned_counts[tid] = assigned_counts.get(tid, 0) + 1
        
        if only_unoccupied:
            # Look for a patch with 0 active miners (occupied_by is None)
            unoccupied = [p for p in patches if p.occupied_by is None]
            if unoccupied:
                # Pick the closest unoccupied one
                best = min(unoccupied, key=lambda p: entity.pos.dist_to_sq(p.pos))
                return best.id
            return None

        # Standard score: (assignment count, square distance)
        best = min(patches, key=lambda p: (assigned_counts.get(p.id, 0), entity.pos.dist_to_sq(p.pos)))
        return best.id
    
    def get_status(self, entity, game_state):
        if self.phase == 'moving_to_patch':
            return 'harvest'
        elif self.phase == 'mining':
            patch = game_state.entities.get(self.target_patch_id)
            if patch and patch.occupied_by is not None and patch.occupied_by != entity.id:
                return 'waiting'
            return 'mining'
        elif self.phase == 'returning':
            return 'return'
        return 'gather'


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
            entity.move_towards(target.pos, game_state)
    
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
            entity.move_towards(self.destination, game_state)
    
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
