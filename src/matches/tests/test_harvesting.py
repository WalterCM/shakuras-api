"""
Tests for harvesting mechanics and resource gathering.
"""
from django.test import TestCase
from matches.engine import Entity, SpatialGrid
from matches.actions import GatherAction


class HarvestingTests(TestCase):
    """Test harvesting mechanics and resource gathering"""

    def test_patch_depletion_mid_mining(self):
        """Test worker behavior when patch depletes while mining"""
        worker = Entity('worker', 'p1', 10, 10)
        patch = Entity('mineral_patch', 'neutral', 15, 10)
        patch.hp = 5  # Very low HP
        base = Entity('base', 'p1', 5, 10)
        
        class MockGameState:
            def __init__(self):
                self.entities = {worker.id: worker, patch.id: patch, base.id: base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        worker.action = GatherAction(patch.id)
        
        # Move to patch
        for _ in range(10):
            if worker.action and worker.action.phase == 'mining':
                break
            worker.update(gs)
        
        # Deplete patch while worker is mining
        patch.hp = 0
        
        # Worker should try to find another patch on next phase transition
        for _ in range(40):
            if worker.action:
                worker.update(gs)
        
        # Worker should have stopped (no other patches available)
        self.assertIsNone(worker.action)

    def test_worker_death_while_carrying(self):
        """Test minerals are dropped when worker dies while carrying"""
        worker = Entity('worker', 'p1', 10, 10)
        worker.carrying = 8
        
        worker.take_damage(1000)
        
        self.assertEqual(worker.hp, 0)
        self.assertEqual(worker.carrying, 0)
        self.assertEqual(worker.get_current_status(), 'dead')

    def test_gather_full_cycle(self):
        """Test complete gather cycle: move -> mine -> return -> repeat"""
        worker = Entity('worker', 'p1', 10, 10)
        patch = Entity('mineral_patch', 'neutral', 15, 10)
        base = Entity('base', 'p1', 5, 10)
        
        class MockGameState:
            def __init__(self):
                self.entities = {worker.id: worker, patch.id: patch, base.id: base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        worker.action = GatherAction(patch.id)
        
        # Phase 1: Moving to patch
        self.assertEqual(worker.action.phase, 'moving_to_patch')
        
        # Run until mining
        for _ in range(10):
            worker.update(gs)
            if worker.action and worker.action.phase == 'mining':
                break
        
        self.assertEqual(worker.action.phase, 'mining')
        self.assertEqual(patch.occupied_by, worker.id)
        
        # Run until returning
        for _ in range(35):
            worker.update(gs)
            if worker.action and worker.action.phase == 'returning':
                break
        
        self.assertEqual(worker.action.phase, 'returning')
        self.assertEqual(worker.carrying, worker.harvest_amount)
        self.assertIsNone(patch.occupied_by)
        
        # Run until back to moving_to_patch
        for _ in range(10):
            worker.update(gs)
            if worker.action and worker.action.phase == 'moving_to_patch':
                break
        
        self.assertEqual(worker.action.phase, 'moving_to_patch')
        self.assertEqual(worker.carrying, 0)
        self.assertGreater(gs.resources['p1'], 0)

    def test_patch_claiming_and_releasing(self):
        """Test that workers claim patches when they arrive and release when done"""
        worker = Entity('worker', 'p1', 10, 10, 'w1')
        patch = Entity('mineral_patch', 'neutral', 15, 10, 'patch1')
        base = Entity('base', 'p1', 5, 10, 'base1')
        
        class MockGameState:
            def __init__(self):
                self.entities = {'w1': worker, 'patch1': patch, 'base1': base}
                self.grid = SpatialGrid(128, 128)
                self.resources = {'p1': 0}
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
        
        gs = MockGameState()
        worker.action = GatherAction(patch.id)
        
        # Verify patch is not occupied initially
        self.assertIsNone(patch.occupied_by)
        
        # Run until worker reaches patch
        for _ in range(10):
            worker.action.update(worker, gs)
            if worker.action.phase == 'mining':
                break
        
        # Verify patch is now occupied
        self.assertEqual(patch.occupied_by, worker.id)
        
        # Wait for mining to complete and verify patch is released
        released_during_return = False
        for _ in range(50):
            if worker.action:
                prev_phase = worker.action.phase
                worker.action.update(worker, gs)
                if prev_phase == 'mining' and worker.action and worker.action.phase == 'returning':
                    if patch.occupied_by is None:
                        released_during_return = True
                        break
        
        self.assertTrue(released_during_return)

    def test_occupied_patch_retargeting(self):
        """Test that workers retarget when patch is occupied"""
        w1 = Entity('worker', 'p1', 10, 10, 'w1')
        w2 = Entity('worker', 'p1', 12, 10, 'w2')
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
        
        # Both workers target patch1 (closer)
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
        """Test worker behavior when all patches are occupied"""
        w1 = Entity('worker', 'p1', 10, 10, 'w1')
        w2 = Entity('worker', 'p1', 12, 10, 'w2')
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
        
        # Worker should still have an action (waiting, not stopped)
        self.assertIsNotNone(w2.action)
        self.assertEqual(w2.action.phase, 'moving_to_patch')

    def test_simultaneous_patch_access(self):
        """Test two workers trying to mine same patch simultaneously"""
        w1 = Entity('worker', 'p1', 10, 10, 'w1')
        w2 = Entity('worker', 'p1', 12, 10, 'w2')
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
        
        # At most one worker should be mining
        mining_workers = []
        if w1.action and w1.action.phase == 'mining':
            mining_workers.append(w1.id)
        if w2.action and w2.action.phase == 'mining':
            mining_workers.append(w2.id)
        self.assertLessEqual(len(mining_workers), 1)
