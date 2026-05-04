"""
Tests for general entity mechanics and edge cases.
"""
from django.test import TestCase
from matches.engine import Entity


class EntityEdgeCaseTests(TestCase):
    """Test edge cases for entity state and mechanics"""

    def test_zero_hp_entity_no_negative(self):
        """Test that HP doesn't go negative"""
        entity = Entity('scv', 'p1', 10, 10)
        entity.take_damage(1000)
        
        self.assertEqual(entity.hp, 0)
        self.assertGreaterEqual(entity.hp, 0)
