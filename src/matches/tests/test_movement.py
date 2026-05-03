"""
Tests for movement, collision, and spatial grid mechanics.
"""
from django.test import TestCase
from matches.engine import Entity, SpatialGrid
from matches.utils import Vector2D
from matches.actions import MoveAction


class MovementAndCollisionTests(TestCase):
    """Test edge cases in movement, collision, and spatial mechanics"""

    def test_move_to_same_position(self):
        """Test moving to current position"""
        entity = Entity('worker', 'p1', 10, 10)
        entity.action = MoveAction(Vector2D(10, 10))
        
        class MockGameState:
            def __init__(self):
                self.entities = {entity.id: entity}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        entity.update(gs)
        
        # Should immediately become idle
        self.assertIsNone(entity.action)
        self.assertEqual(entity.pos.x, 10)
        self.assertEqual(entity.pos.y, 10)

    def test_entity_radius_collision(self):
        """Test that entities with different radii collide correctly"""
        # Marine (radius 0.5) and Worker (radius 0.5)
        marine = Entity('marine', 'p1', 10, 10)
        worker = Entity('worker', 'p1', 10.5, 10)  # Very close
        
        class MockGameState:
            def __init__(self):
                self.entities = {marine.id: marine, worker.id: worker}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        gs.grid.insert(marine)
        gs.grid.insert(worker)
        
        initial_dist = marine.pos.dist_to(worker.pos)
        
        # Apply repulsion
        marine.update(gs)
        
        # Distance should increase due to repulsion
        final_dist = marine.pos.dist_to(worker.pos)
        # Marine should be pushed away since they're overlapping
        # (distance 0.5 < combined radii of 1.0)
        self.assertGreater(final_dist, initial_dist)

    def test_spatial_grid_boundary(self):
        """Test spatial grid at map boundaries"""
        grid = SpatialGrid(64, 64, cell_size=8.0)
        
        # Entity at corner
        e1 = Entity('worker', 'p1', 0, 0, 'e1')
        grid.insert(e1)
        
        # Entity at opposite corner
        e2 = Entity('worker', 'p2', 63, 63, 'e2')
        grid.insert(e2)
        
        # Should not find each other
        nearby_e1 = grid.get_nearby_ids(e1.pos)
        nearby_e2 = grid.get_nearby_ids(e2.pos)
        
        self.assertIn(e1.id, nearby_e1)
        self.assertNotIn(e2.id, nearby_e1)
        self.assertIn(e2.id, nearby_e2)
        self.assertNotIn(e1.id, nearby_e2)
