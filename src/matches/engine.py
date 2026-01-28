import uuid
import random
import json
import math
from .data import UNIT_STATS

class Entity:
    """Represents a single unit or building in the game world"""
    def __init__(self, unit_type, owner_id, x, y, entity_id=None):
        self.id = entity_id or str(uuid.uuid4())[:8]
        self.type = unit_type
        self.owner_id = owner_id
        self.pos_x = x
        self.pos_y = y
        self.status = 'idle' # idle, move, attack, harvest, dead
        self.target_id = None
        self.destination = None
        
        # Load stats from data.py
        stats = UNIT_STATS.get(unit_type, UNIT_STATS['worker'])
        self.hp = stats['hp']
        self.max_hp = stats['hp']
        self.damage = stats['damage']
        self.range = stats['range']
        self.cooldown = stats['cooldown']
        self.speed = stats['speed']
        self.current_cooldown = 0

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'owner_id': self.owner_id,
            'x': round(self.pos_x, 2),
            'y': round(self.pos_y, 2),
            'hp': self.hp,
            'status': self.status
        }

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.status = 'dead'

    def update(self, game_state):
        """Update entity state based on current logic"""
        if self.status == 'dead':
            return

        if self.current_cooldown > 0:
            self.current_cooldown -= 1

        if self.status == 'move' and self.destination:
            self._handle_move()
        elif self.status == 'attack' and self.target_id:
            self._handle_attack(game_state)
        elif self.status == 'idle':
            # Potentially find something to do
            pass

    def _handle_move(self):
        target_x, target_y = self.destination
        dx = target_x - self.pos_x
        dy = target_y - self.pos_y
        dist = math.sqrt(dx**2 + dy**2)

        if dist < self.speed:
            self.pos_x = target_x
            self.pos_y = target_y
            self.status = 'idle'
            self.destination = None
        else:
            self.pos_x += (dx / dist) * self.speed
            self.pos_y += (dy / dist) * self.speed

    def _handle_attack(self, game_state):
        target = game_state.entities.get(self.target_id)
        if not target or target.status == 'dead':
            self.status = 'idle'
            self.target_id = None
            return

        dx = target.pos_x - self.pos_x
        dy = target.pos_y - self.pos_y
        dist = math.sqrt(dx**2 + dy**2)

        if dist <= self.range:
            if self.current_cooldown <= 0:
                target.take_damage(self.damage)
                self.current_cooldown = self.cooldown
        else:
            # Move towards target if out of range
            move_dist = dist - self.range + 0.1
            self.pos_x += (dx / dist) * min(self.speed, move_dist)
            self.pos_y += (dy / dist) * min(self.speed, move_dist)

class MatchSimulator:
    """Handles the simulation loop of a match using JSON Deltas for efficiency"""
    def __init__(self, player1, player2, max_ticks=100):
        self.player1 = player1
        self.player2 = player2
        self.max_ticks = max_ticks
        self.entities = {} # Use dict for fast lookup by ID
        self.history = [] # Stores deltas

    def _setup_initial_entities(self):
        # Add basic bases logic (hardcoded for now)
        self._add_entity(Entity('base', self.player1.id, 10, 10))
        self._add_entity(Entity('base', self.player2.id, 90, 90))
        
        for i in range(4):
            # Marines for the players
            self._add_entity(Entity('marine', self.player1.id, 15 + i, 15))
            self._add_entity(Entity('marine', self.player2.id, 85 - i, 85))

    def _add_entity(self, entity):
        self.entities[entity.id] = entity

    def simulate(self):
        """Runs the simulation and returns delta-based JSON history"""
        self._setup_initial_entities()
        
        # Give initial orders to test movement/combat
        # Player 1's marines move toward Player 2's base
        for ent in self.entities.values():
            if ent.owner_id == self.player1.id and ent.type == 'marine':
                ent.status = 'attack'
                ent.target_id = [e.id for e in self.entities.values() if e.owner_id == self.player2.id and e.type == 'base'][0]
            elif ent.owner_id == self.player2.id and ent.type == 'marine':
                ent.status = 'attack'
                ent.target_id = [e.id for e in self.entities.values() if e.owner_id == self.player1.id and e.type == 'base'][0]

        # Initial State (Tick 0)
        initial_state = [e.to_dict() for e in self.entities.values()]
        self.history.append({'tick': 0, 'entities': initial_state})

        for tick in range(1, self.max_ticks):
            tick_deltas = []
            
            # Create a snapshot of important states before update
            pre_update = {ent_id: (ent.pos_x, ent.pos_y, ent.hp, ent.status) 
                         for ent_id, ent in self.entities.items()}

            # Update all entities
            for ent in list(self.entities.values()):
                ent.update(self)

            # Record deltas
            for ent_id, ent in self.entities.items():
                old_x, old_y, old_hp, old_status = pre_update[ent_id]
                
                if (abs(ent.pos_x - old_x) > 0.01 or 
                    abs(ent.pos_y - old_y) > 0.01 or 
                    ent.hp != old_hp or 
                    ent.status != old_status):
                    
                    delta = {'id': ent_id}
                    if abs(ent.pos_x - old_x) > 0.01: delta['x'] = round(ent.pos_x, 2)
                    if abs(ent.pos_y - old_y) > 0.01: delta['y'] = round(ent.pos_y, 2)
                    if ent.hp != old_hp: delta['hp'] = ent.hp
                    if ent.status != old_status: delta['status'] = ent.status
                    
                    tick_deltas.append(delta)
            
            if tick_deltas:
                self.history.append({'tick': tick, 'entities': tick_deltas})

            # Cleanup dead entities (optional, maybe keep for final snapshot)
            # For now, we keep them but they stop updating

        return self.history
