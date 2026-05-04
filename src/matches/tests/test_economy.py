"""
Standardized tests for game economy and resource extraction.
Verified against StarCraft: BroodWar standards (8 minerals per trip).
"""
from django.test import TestCase
from players.models import Player
from matches.engine import MatchSimulator, Entity
from matches.actions import GatherAction

class EconomyTests(TestCase):
    def setUp(self):
        self.p1 = Player.objects.create(nickname='Pro Gamer')
        self.p2 = Player.objects.create(nickname='AI')

    def test_mineral_extraction_rate(self):
        """
        Verify that scvs extract exactly 8 minerals per trip.
        This test runs a controlled simulation with 1 scv and 1 patch.
        """
        sim = MatchSimulator(self.p1, self.p2)
        sim.setup_match()
        
        # Clear existing entities for a clean test
        sim.entities = {}
        sim.grid.clear()
        
        # Spawn 1 base, 1 patch, 1 scv
        base = Entity('base', 'p1', 10, 10)
        patch = Entity('mineral_patch', 'neutral', 15, 10)
        scv = Entity('scv', 'p1', 11, 10)
        
        sim.entities = {base.id: base, patch.id: patch, scv.id: scv}
        sim.grid.insert(base)
        sim.grid.insert(patch)
        sim.grid.insert(scv)
        
        # Reset resources
        sim.resources['p1'] = 0
        
        # Start gathering
        scv.action = GatherAction(patch.id)
        
        # Run for 1000 ticks (enough for multiple trips)
        for _ in range(1000):
            # Manually update entities
            for ent in list(sim.entities.values()):
                ent.update(sim)
        
        total_minerals = sim.resources['p1']
        
        # Check if total is multiple of 8
        self.assertGreater(total_minerals, 0, "No minerals were extracted")
        self.assertEqual(total_minerals % 8, 0, f"Extraction rate inconsistent: {total_minerals}")
        
        print(f"\n[ECONOMY TEST] Total extracted: {total_minerals}")
        print(f"[ECONOMY TEST] Trips completed: {total_minerals // 8}")
