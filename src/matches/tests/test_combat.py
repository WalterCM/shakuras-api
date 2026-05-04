"""
Tests for combat mechanics and attack behavior edge cases.
"""
from django.test import TestCase
from matches.engine import Entity, SpatialGrid
from matches.utils import Vector2D
from matches.actions import AttackAction, HoldAction


class CombatEdgeCaseTests(TestCase):
    """Test edge cases in combat and attack mechanics"""

    def test_attack_out_of_range_target(self):
        """Test attacker behavior when target moves out of range"""
        attacker = Entity('marine', 'p1', 0, 0)
        target = Entity('scv', 'p2', 3, 0)  # Within range initially
        
        class MockGameState:
            def __init__(self):
                self.entities = {attacker.id: attacker, target.id: target}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        attacker.action = AttackAction(target.id)
        
        # First attack should work
        attacker.update(gs)
        initial_hp = target.hp
        
        # Move target far away
        target.pos = Vector2D(100, 100)
        
        # Attacker should chase
        for _ in range(5):
            attacker.update(gs)
        
        # Attacker should be moving towards target
        self.assertGreater(attacker.pos.x, 0)
        self.assertGreater(attacker.pos.y, 0)

    def test_attack_dead_target(self):
        """Test attacker behavior when target dies"""
        attacker = Entity('marine', 'p1', 0, 0)
        target = Entity('scv', 'p2', 3, 0)
        
        class MockGameState:
            def __init__(self):
                self.entities = {attacker.id: attacker, target.id: target}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        attacker.action = AttackAction(target.id)
        
        # Kill target
        target.take_damage(1000)
        
        # Attacker should stop
        attacker.update(gs)
        self.assertIsNone(attacker.action)

    def test_hold_position_with_no_enemies(self):
        """Test HoldAction when no enemies nearby"""
        entity = Entity('marine', 'p1', 10, 10)
        entity.action = HoldAction()
        
        class MockGameState:
            def __init__(self):
                self.entities = {entity.id: entity}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        gs.grid.insert(entity)
        
        initial_pos = Vector2D(entity.pos.x, entity.pos.y)
        
        # Run for several ticks
        for _ in range(10):
            entity.update(gs)
        
        # Should not move
        self.assertEqual(entity.pos.x, initial_pos.x)
        self.assertEqual(entity.pos.y, initial_pos.y)

    def test_attack_chase_and_engage(self):
        """Test attack transitions from chase to engage"""
        attacker = Entity('marine', 'p1', 0, 0)
        target = Entity('scv', 'p2', 20, 0)  # Far away
        
        class MockGameState:
            def __init__(self):
                self.entities = {attacker.id: attacker, target.id: target}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        attacker.action = AttackAction(target.id)
        
        # Should be chasing
        self.assertEqual(attacker.get_current_status(), 'attack')
        
        # Run until in range
        for _ in range(20):
            attacker.update(gs)
            dist = attacker.pos.dist_to(target.pos)
            if dist <= attacker.range + attacker.radius + target.radius:
                break
        
        initial_target_hp = target.hp
        
        # Should attack
        attacker.update(gs)
        self.assertLess(target.hp, initial_target_hp)
