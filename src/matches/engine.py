import uuid
import random
import json

class Entity:
    """Represents a single unit or building in the game world"""
    def __init__(self, unit_type, owner_id, x, y, hp, entity_id=None):
        self.id = entity_id or str(uuid.uuid4())[:8]
        self.type = unit_type
        self.owner_id = owner_id
        self.pos_x = x
        self.pos_y = y
        self.hp = hp
        self.status = 'idle'
        self.target_id = None

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
        self._add_entity(Entity('base', self.player1.id, 10, 10, 1500))
        self._add_entity(Entity('base', self.player2.id, 90, 90, 1500))
        
        for i in range(4):
            self._add_entity(Entity('worker', self.player1.id, 12 + i, 12, 40))
            self._add_entity(Entity('worker', self.player2.id, 88 - i, 88, 40))

    def _add_entity(self, entity):
        self.entities[entity.id] = entity

    def simulate(self):
        """Runs the simulation and returns delta-based JSON history"""
        self._setup_initial_entities()
        
        # Initial State (Tick 0) - Always full snapshot of all entities
        initial_state = [e.to_dict() for e in self.entities.values()]
        self.history.append({'tick': 0, 'entities': initial_state})

        for tick in range(1, self.max_ticks):
            tick_deltas = []
            
            for ent_id, ent in self.entities.items():
                old_x, old_y = ent.pos_x, ent.pos_y
                old_hp = ent.hp
                
                # Simple placeholder movement logic toward the center (50, 50)
                # Only units move, buildings (bases) stay stationary
                if ent.type != 'base':
                    dx = (50 - ent.pos_x) * 0.05
                    dy = (50 - ent.pos_y) * 0.05
                    
                    ent.pos_x += dx + random.uniform(-1, 1)
                    ent.pos_y += dy + random.uniform(-1, 1)
                
                # Record deltas only if state changed significantly
                if abs(ent.pos_x - old_x) > 0.01 or abs(ent.pos_y - old_y) > 0.01 or ent.hp != old_hp:
                    tick_deltas.append({
                        'id': ent_id,
                        'x': round(ent.pos_x, 2),
                        'y': round(ent.pos_y, 2),
                        'hp': ent.hp
                    })
            
            if tick_deltas:
                self.history.append({'tick': tick, 'entities': tick_deltas})

        return self.history
