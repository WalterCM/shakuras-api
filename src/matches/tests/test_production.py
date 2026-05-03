"""
Tests for production mechanics and unit spawning.
"""
from django.test import TestCase
from players.models import Player
from matches.engine import MatchSimulator


class ProductionEdgeCaseTests(TestCase):
    """Test edge cases in unit production and queue management"""

    def test_production_queue_overflow(self):
        """Test behavior when queuing many units"""
        p1 = Player.objects.create(nickname='P1')
        p2 = Player.objects.create(nickname='P2')
        sim = MatchSimulator(p1, p2)
        sim.setup_match()
        
        # Give lots of minerals
        sim.resources['p1'] = 1000
        
        # Queue 5 marines (max queue size is 5, cost 50 each = 250 total)
        for i in range(5):
            success = sim.request_unit('p1', 'marine')
            self.assertTrue(success, f"Failed to queue marine {i+1}")
        
        base = [e for e in sim.entities.values() if e.owner_id == 'p1' and e.type == 'base'][0]
        self.assertEqual(len(base.production_queue), 5)
        # Should have spent 250 minerals
        self.assertEqual(sim.resources['p1'], 750)
        
        # Trying to queue a 6th should fail (queue is full)
        success = sim.request_unit('p1', 'marine')
        self.assertFalse(success)
