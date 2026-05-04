"""
Tests for harvesting mechanics and resource gathering.
"""
from django.test import TestCase
from matches.engine import Entity, SpatialGrid
from matches.actions import GatherAction


class HarvestingTests(TestCase):
    """Test harvesting mechanics and resource gathering"""

    def test_patch_depletion_mid_mining(self):
        """Test scv behavior when patch depletes while mining"""
        scv = Entity('scv', 'p1', 10, 10)
        patch = Entity('mineral_patch', 'neutral', 15, 10)
        patch.hp = 5  # Very low HP
        base = Entity('base', 'p1', 5, 10)
        
        class MockGameState:
            def __init__(self):
                self.entities = {scv.id: scv, patch.id: patch, base.id: base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        scv.action = GatherAction(patch.id)
        
        # Move to patch
        for _ in range(10):
            if scv.action and scv.action.phase == 'mining':
                break
            scv.update(gs)
        
        # Deplete patch while scv is mining
        patch.hp = 0
        
        # scv should try to find another patch on next phase transition
        for _ in range(40):
            if scv.action:
                scv.update(gs)
        
        # scv should have stopped (no other patches available)
        self.assertIsNone(scv.action)

    def test_scv_death_while_carrying(self):
        """Test minerals are dropped when scv dies while carrying"""
        scv = Entity('scv', 'p1', 10, 10)
        scv.carrying = 8
        
        scv.take_damage(1000)
        
        self.assertEqual(scv.hp, 0)
        self.assertEqual(scv.carrying, 0)
        self.assertEqual(scv.get_current_status(), 'dead')

    def test_gather_full_cycle(self):
        """Test complete gather cycle: move -> mine -> return -> repeat"""
        scv = Entity('scv', 'p1', 10, 10)
        patch = Entity('mineral_patch', 'neutral', 15, 10)
        base = Entity('base', 'p1', 5, 10)
        
        class MockGameState:
            def __init__(self):
                self.entities = {scv.id: scv, patch.id: patch, base.id: base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        scv.action = GatherAction(patch.id)
        
        # Phase 1: Moving to patch
        self.assertEqual(scv.action.phase, 'moving_to_patch')
        
        # Run until mining
        for _ in range(10):
            scv.update(gs)
            if scv.action and scv.action.phase == 'mining':
                break
        
        self.assertEqual(scv.action.phase, 'mining')
        self.assertEqual(patch.occupied_by, scv.id)
        
        # Run until returning
        for _ in range(35):
            scv.update(gs)
            if scv.action and scv.action.phase == 'returning':
                break
        
        self.assertEqual(scv.action.phase, 'returning')
        self.assertEqual(scv.carrying, scv.harvest_amount)
        self.assertIsNone(patch.occupied_by)
        
        # Run until back to moving_to_patch
        for _ in range(10):
            scv.update(gs)
            if scv.action and scv.action.phase == 'moving_to_patch':
                break
        
        self.assertEqual(scv.action.phase, 'moving_to_patch')
        self.assertEqual(scv.carrying, 0)
        self.assertGreater(gs.resources['p1'], 0)

    def test_patch_claiming_and_releasing(self):
        """Test that scvs claim patches when they arrive and release when done"""
        scv = Entity('scv', 'p1', 10, 10, 'w1')
        patch = Entity('mineral_patch', 'neutral', 15, 10, 'patch1')
        base = Entity('base', 'p1', 5, 10, 'base1')
        
        class MockGameState:
            def __init__(self):
                self.entities = {'w1': scv, 'patch1': patch, 'base1': base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        scv.action = GatherAction(patch.id)
        
        # Verify patch is not occupied initially
        self.assertIsNone(patch.occupied_by)
        
        # Run until scv reaches patch
        for _ in range(10):
            scv.action.update(scv, gs)
            if scv.action.phase == 'mining':
                break
        
        # Verify patch is now occupied
        self.assertEqual(patch.occupied_by, scv.id)
        
        # Wait for mining to complete and verify patch is released
        released_during_return = False
        for _ in range(50):
            if scv.action:
                prev_phase = scv.action.phase
                scv.action.update(scv, gs)
                if prev_phase == 'mining' and scv.action and scv.action.phase == 'returning':
                    if patch.occupied_by is None:
                        released_during_return = True
                        break
        
        self.assertTrue(released_during_return)

    def test_occupied_patch_retargeting(self):
        """Test that scvs retarget when patch is occupied"""
        w1 = Entity('scv', 'p1', 10, 10, 'w1')
        w2 = Entity('scv', 'p1', 12, 10, 'w2')
        patch1 = Entity('mineral_patch', 'neutral', 20, 10, 'patch1')
        patch2 = Entity('mineral_patch', 'neutral', 30, 10, 'patch2')
        
        class MockGameState:
            def __init__(self):
                self.entities = {'w1': w1, 'w2': w2, 'patch1': patch1, 'patch2': patch2}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        
        # Both scvs target patch1 (closer)
        w1.action = GatherAction(patch1.id)
        w2.action = GatherAction(patch1.id)
        
        # Run until w1 reaches patch1
        for _ in range(15):
            w1.action.update(w1, gs)
            if w1.action.phase == 'mining':
                break
        
        self.assertEqual(patch1.occupied_by, w1.id)
        
        # Now w2 tries to reach patch1 but should retarget
        for _ in range(5):
            w2.action.update(w2, gs)
        
        # W2 should have retargeted to patch2
        self.assertEqual(w2.action.target_patch_id, patch2.id)

    def test_no_available_patches(self):
        """Test scv behavior when all patches are occupied"""
        w1 = Entity('scv', 'p1', 10, 10, 'w1')
        w2 = Entity('scv', 'p1', 12, 10, 'w2')
        patch = Entity('mineral_patch', 'neutral', 20, 10, 'patch1')
        
        class MockGameState:
            def __init__(self):
                self.entities = {'w1': w1, 'w2': w2, 'patch1': patch}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        
        # Both target the same patch
        w1.action = GatherAction(patch.id)
        w2.action = GatherAction(patch.id)
        
        # W1 reaches first
        for _ in range(15):
            w1.action.update(w1, gs)
            if w1.action.phase == 'mining':
                break
        
        self.assertEqual(patch.occupied_by, w1.id)
        
        # W2 tries but should wait (action still exists, but not moving)
        # It stays in 'moving_to_patch' phase waiting for patch to free up
        for _ in range(5):
            if w2.action:
                w2.action.update(w2, gs)
        
        # scv should still have an action (waiting, not stopped)
        self.assertIsNotNone(w2.action)
        self.assertEqual(w2.action.phase, 'moving_to_patch')

    def test_simultaneous_patch_access(self):
        """Test two scvs trying to mine same patch simultaneously"""
        w1 = Entity('scv', 'p1', 10, 10, 'w1')
        w2 = Entity('scv', 'p1', 12, 10, 'w2')
        patch = Entity('mineral_patch', 'neutral', 15, 10, 'patch1')
        base = Entity('base', 'p1', 5, 10)
        
        class MockGameState:
            def __init__(self):
                self.entities = {'w1': w1, 'w2': w2, 'patch1': patch, 'base': base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        w1.action = GatherAction(patch.id)
        w2.action = GatherAction(patch.id)
        
        # Run until both try to reach patch
        for _ in range(10):
            w1.update(gs)
            w2.update(gs)
        
        # Only one should be mining the patch at a time
        if w1.action and w1.action.phase == 'mining':
            self.assertTrue(patch.occupied_by is None or patch.occupied_by == w1.id)
        if w2.action and w2.action.phase == 'mining':
            self.assertTrue(patch.occupied_by is None or patch.occupied_by == w2.id)
        
        # At most one scv should be mining
        mining_scvs = []
        if w1.action and w1.action.phase == 'mining':
            mining_scvs.append(w1.id)
        if w2.action and w2.action.phase == 'mining':
            mining_scvs.append(w2.id)
        self.assertLessEqual(len(mining_scvs), 1)
