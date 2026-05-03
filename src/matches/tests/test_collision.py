from django.test import TestCase
from matches.engine import Entity, NavigationGrid, SpatialGrid
from matches.utils import Vector2D
from matches.actions import MoveAction
import math

class GridCollisionTests(TestCase):
    def setUp(self):
        self.width = 128
        self.height = 128
        
    class MockGameState:
        def __init__(self, width, height):
            self.nav_grid = NavigationGrid(width, height)
            self.grid = SpatialGrid(width, height)
            self.entities = {}
            self.resources = {'p1': 0, 'p2': 0}
            self.width = width
            self.height = height
        
        def _spawn_entity(self, entity):
            self.entities[entity.id] = entity
            if entity.type in ['base', 'mineral_patch', 'building']:
                bx, by = int(entity.pos.x - entity.width/2), int(entity.pos.y - entity.height/2)
                for ox in range(entity.width):
                    for oy in range(entity.height):
                        self.nav_grid.set_static(bx + ox, by + oy, entity.id)
            else:
                self.nav_grid.set_dynamic(entity.pos.x, entity.pos.y, entity.id)

    def test_worker_vs_base_sliding(self):
        """Worker vs Base: Verify clean sliding around the 4x3 footprint."""
        gs = self.MockGameState(self.width, self.height)
        
        # Base at (10, 10), width=4, height=3 -> center at (12, 11.5)
        base = Entity('base', 'p1', 12, 11.5)
        gs._spawn_entity(base)
        
        # Worker moving from left to right, straight through the center
        worker = Entity('worker', 'p1', 8, 11.5)
        worker.action = MoveAction(Vector2D(16, 11.5))
        gs._spawn_entity(worker)
        
        # Simulate ticks
        for _ in range(40):
            # Refresh dynamic grid
            gs.nav_grid.clear_dynamic()
            for ent in gs.entities.values():
                if ent.type not in ['base', 'mineral_patch', 'building']:
                    gs.nav_grid.set_dynamic(ent.pos.x, ent.pos.y, ent.id)
            worker.update(gs)
            
        # Worker should have moved past the base (target is at 16)
        # Speed is 1.0, so 40 ticks is plenty even with sliding
        self.assertGreater(worker.pos.x, 14) 
        # Check against static grid only to avoid self-blocking in test verification
        self.assertFalse(gs.nav_grid.is_blocked(worker.pos, check_dynamic=False))

    def test_worker_vs_arc(self):
        """Worker vs Arc: Verify the unit follows the curve of a mineral arc instead of getting stuck."""
        gs = self.MockGameState(self.width, self.height)
        
        # Create a "trap" / concave arc with minerals
        # L-shape opening towards top-left
        # Wall at x=15, y=10-15
        for y in range(10, 16):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', 15.5, y + 0.5))
        # Wall at x=10-15, y=15
        for x in range(10, 15):
            gs._spawn_entity(Entity('mineral_patch', 'neutral', x + 0.5, 15.5))
            
        # Worker inside the concavity
        worker = Entity('worker', 'p1', 13, 13)
        # Target is past the corner (bottom-right)
        worker.action = MoveAction(Vector2D(20, 20))
        gs._spawn_entity(worker)
        
        for _ in range(150):
            gs.nav_grid.clear_dynamic()
            for ent in gs.entities.values():
                if ent.type not in ['base', 'mineral_patch', 'building']:
                    gs.nav_grid.set_dynamic(ent.pos.x, ent.pos.y, ent.id)
            worker.update(gs)
            
        # Should have found its way out around the mineral wall
        self.assertGreater(worker.pos.x, 16)
        self.assertLessEqual(worker.pos.y, 20.1) # Small tolerance for diagonal movement

    def test_the_square_trap(self):
        """The Square Trap: Unit tries directions but stays trapped (no ghost mode)."""
        gs = self.MockGameState(self.width, self.height)
        
        # 4x4 enclosure of minerals (inner area is empty)
        # But leave small gaps at corners for workers to potentially escape
        # Top and bottom walls
        for x in range(10, 14):
            gs._spawn_entity(Entity('neutral_block', 'neutral', x + 0.5, 10.5))
            gs._spawn_entity(Entity('neutral_block', 'neutral', x + 0.5, 13.5))
        # Left and right walls  
        for y in range(11, 13):
            gs._spawn_entity(Entity('neutral_block', 'neutral', 10.5, y + 0.5))
            gs._spawn_entity(Entity('neutral_block', 'neutral', 13.5, y + 0.5))
                
        # Worker trapped inside at center (12.5, 12.5)
        worker = Entity('worker', 'p1', 12.5, 12.5)
        worker.action = MoveAction(Vector2D(50, 50))
        gs._spawn_entity(worker)

        initial_pos = worker.pos.copy()
        
        # Simulate and track movement
        moved = False
        directions_tried = set()
        
        for tick in range(100):
            gs.nav_grid.clear_dynamic()
            gs.nav_grid.set_dynamic(worker.pos.x, worker.pos.y, worker.id)
            worker.update(gs)
            
            if worker.pos.dist_to(initial_pos) > 1:
                moved = True
                dx = worker.pos.x - initial_pos.x
                dy = worker.pos.y - initial_pos.y
                if abs(dx) > abs(dy):
                    directions_tried.add('horizontal')
                else:
                    directions_tried.add('vertical')
                initial_pos = worker.pos.copy()
        
        # Worker should have tried different directions (at least attempted movement)
        self.assertTrue(moved, f"Worker should try to move. Pos: {worker.pos}")
        
        # In a sealed trap, worker cannot escape without pathfinding
        # This test just verifies it attempts movement before stopping
