from django.test import TestCase, RequestFactory
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from matches.models import Match, MatchParticipant, Replay
from players.models import Player
from teams.models import Team
from matches.serializers import MatchSerializer
from matches.engine import Entity, MatchSimulator, SpatialGrid, Map
from matches.utils import Vector2D
from matches.actions import MoveAction, AttackAction, GatherAction
import math
from matches.data import UNIT_STATS

MATCHES_URL = reverse('matches:match-list')

def detail_url(match_id):
    """Return match detail URL"""
    return reverse('matches:match-detail', args=[match_id])

class PublicMatchApiTests(TestCase):
    """Test public match API access"""

    def setUp(self):
        self.client = APIClient()

    def test_retrieve_matches_successful(self):
        """Test retrieving match list"""
        Match.objects.create(date='2026-01-27T12:00:00Z', status=Match.STATUS.IDLE)
        Match.objects.create(date='2026-01-28T12:00:00Z', status=Match.STATUS.ONGOING)

        res = self.client.get(MATCHES_URL)

        matches = Match.objects.all().order_by('-date')
        serializer = MatchSerializer(matches, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_match_detail(self):
        """Test retrieving a specific match detail"""
        player = Player.objects.create(nickname='Flash', first_name='Lee', last_name='Young Ho', country='Korea')
        match = Match.objects.create(date='2026-01-27T12:00:00Z', status=Match.STATUS.FINISHED)
        MatchParticipant.objects.create(
            match=match,
            participant=player,
            score='3'
        )

        url = detail_url(match.id)
        res = self.client.get(url)

        serializer = MatchSerializer(match)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)
        self.assertEqual(len(res.data['participants']), 1)
        self.assertEqual(res.data['participants'][0]['participant']['nickname'], 'Flash')


class ReplayViewTests(TestCase):
    """Test the replay visualizer view"""

    def setUp(self):
        self.factory = RequestFactory()
        self.match = Match.objects.create(
            date='2026-01-27T12:00:00Z',
            status=Match.STATUS.FINISHED
        )
        self.replay = Replay.objects.create(
            match=self.match,
            log=[{"tick": 0, "entities": []}]
        )

    def test_visualizer_view_success(self):
        """Test that the visualizer view is accessible"""
        url = reverse('matches:visualizer', args=[self.match.id])
        request = self.factory.get(url)
        
        from matches.views import ReplayView
        view = ReplayView.as_view()
        res = view(request, pk=self.match.id)

        self.assertEqual(res.status_code, 200)
        # We can still check the context on the response if it's a TemplateResponse
        self.assertEqual(res.context_data['match'], self.match)
        # Render the response to check content
        res.render()
        self.assertIn(f'Match #{self.match.id}', res.content.decode())
        self.assertIn('replay-canvas', res.content.decode())


class EngineCoreTests(TestCase):
    """Test the core logic of the Match Engine"""

    def test_entity_stats_initialization(self):
        """Verify Entity loads correct stats from data.py"""
        entity = Entity('marine', 'p1', 10, 10)
        stats = UNIT_STATS['marine']
        
        self.assertEqual(entity.hp, stats['hp'])
        self.assertEqual(entity.damage, stats['damage'])
        self.assertEqual(entity.range, stats['range'])
        self.assertEqual(entity.speed, stats['speed'])
        self.assertEqual(entity.get_current_status(), 'idle')

    def test_entity_take_damage(self):
        """Verify HP reduction and 'dead' status"""
        entity = Entity('marine', 'p1', 10, 10)
        initial_hp = entity.hp
        
        entity.take_damage(10)
        self.assertEqual(entity.hp, initial_hp - 10)
        self.assertNotEqual(entity.get_current_status(), 'dead')
        
        entity.take_damage(initial_hp)
        self.assertEqual(entity.hp, 0)
        self.assertEqual(entity.get_current_status(), 'dead')

    def test_entity_movement(self):
        """Verify pos updates correctly in 'move' state"""
        entity = Entity('worker', 'p1', 0, 0)
        entity.action = MoveAction(Vector2D(10, 10))
        
        # Speed is 1.8, so it should move towards (10,10)
        class MockGS:
            def __init__(self):
                self.entities = {}
                self.grid = SpatialGrid(128, 128)
        
        mgs = MockGS()
        entity.update(mgs)
        
        self.assertGreater(entity.pos.x, 0)
        self.assertGreater(entity.pos.y, 0)
        self.assertLess(entity.pos.x, 10)
        
        # Many ticks to reach destination
        for _ in range(20):
            entity.update(mgs)
            
        self.assertEqual(entity.pos.x, 10)
        self.assertEqual(entity.pos.y, 10)
        self.assertEqual(entity.get_current_status(), 'idle')

    def test_entity_combat(self):
        """Verify target HP reduction and cooldown management"""
        p1_id = 'p1'
        p2_id = 'p2'
        
        attacker = Entity('marine', p1_id, 0, 0)
        target = Entity('base', p2_id, 2, 0) # Within range (4)
        
        # Setup simulator-like context
        class MockGameState:
            def __init__(self):
                self.entities = {target.id: target}
                self.grid = SpatialGrid(128, 128)
        
        game_state = MockGameState()
        attacker.action = AttackAction(target.id)
        
        initial_target_hp = target.hp
        
        # First attack
        attacker.update(game_state)
        
        self.assertEqual(target.hp, initial_target_hp - attacker.damage)
        self.assertGreater(attacker.current_cooldown, 0)
        
        # Immediate second update should NOT deal damage (on cooldown)
        attacker.update(game_state)
        self.assertEqual(target.hp, initial_target_hp - attacker.damage)

    def test_simulator_delta_generation(self):
        """Verify only changed fields are recorded in history"""
        player1 = Player.objects.create(nickname='P1')
        player2 = Player.objects.create(nickname='P2')
        
        sim = MatchSimulator(player1, player2, max_ticks=5)
        sim.setup_match()
        history = sim.simulate()
        
        # Tick 0 should have full snapshots
        self.assertEqual(history[0]['tick'], 0)
        self.assertIn('map', history[0])
        self.assertEqual(history[0]['map']['width'], 128)
        self.assertIn('x', history[0]['entities'][0])
        self.assertIn('y', history[0]['entities'][0])
        self.assertIn('hp', history[0]['entities'][0])
        self.assertIn('type', history[0]['entities'][0])
        
        # Subsequent ticks should be deltas (only if something changed)
        if len(history) > 1:
            for tick_data in history[1:]:
                for entity_delta in tick_data['entities']:
                    self.assertIn('id', entity_delta)
                    # We shouldn't see 'type' or 'owner_id' in deltas usually unless they change (which they don't here)
                    self.assertNotIn('type', entity_delta)
                    self.assertNotIn('owner_id', entity_delta)

    def test_harvest_income(self):
        """Verify that a worker only deposits minerals at a base after mining"""
        player1 = Player.objects.create(nickname='P1')
        player2 = Player.objects.create(nickname='P2')
        
        worker = Entity('worker', 'p1', 0, 0)
        patch = Entity('mineral_patch', 'neutral', 5, 0) # Close to worker
        base = Entity('base', 'p1', 10, 0)
        
        class MockGameState:
            def __init__(self, resources):
                self.entities = {patch.id: patch, worker.id: worker, base.id: base}
                self.resources = resources
                self.grid = SpatialGrid(128, 128)
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
                
        resources = {'p1': 50.0}
        gs = MockGameState(resources)
        
        worker.action = GatherAction(patch.id)
        
        # 1. Move to patch and mine
        # Run until worker reaches patch and starts mining
        for _ in range(10):
            worker.update(gs)
            if worker.get_current_status() == 'mining':
                break
        
        # Continue mining until worker picks up minerals (takes ~30 ticks)
        for _ in range(35):
            worker.update(gs)
            if worker.carrying > 0:
                break
            
        # Should now be carrying minerals and in 'return' state
        self.assertEqual(worker.carrying, worker.harvest_amount)
        self.assertEqual(worker.get_current_status(), 'return')
        self.assertEqual(resources['p1'], 50.0) # Not deposited yet!

        # 2. Return trip
        while worker.get_current_status() == 'return':
            worker.update(gs)
            
        # Should have deposited
        self.assertEqual(resources['p1'], 50.0 + worker.harvest_amount)
        self.assertEqual(worker.carrying, 0)
        self.assertEqual(worker.get_current_status(), 'harvest')

    def test_interrupted_trip(self):
        """Verify that killing a worker carrying minerals drops them"""
        worker = Entity('worker', 'p1', 0, 0)
        worker.carrying = 8
        worker.get_current_status() # Initialize action if any
        
        worker.take_damage(40) # Death
        self.assertEqual(worker.get_current_status(), 'dead')
        self.assertEqual(worker.carrying, 0)

    def test_unit_production_spending(self):
        """Verify minerals are deducted when queuing a unit"""
        p1 = Player.objects.create(nickname='P1')
        p2 = Player.objects.create(nickname='P2')
        sim = MatchSimulator(p1, p2)
        sim.setup_match()
        
        sim.resources['p1'] = 100
        success = sim.request_unit('p1', 'marine')
        
        self.assertTrue(success)
        self.assertEqual(sim.resources['p1'], 50) # Marine cost = 50
        
        # Check base queue
        base = [e for e in sim.entities.values() if e.owner_id == 'p1' and e.type == 'base'][0]
        self.assertEqual(base.production_queue[0], 'marine')

    def test_unit_production_timing(self):
        """Verify unit spawns after build time ticks"""
        p1 = Player.objects.create(nickname='P1')
        p2 = Player.objects.create(nickname='P2')
        sim = MatchSimulator(p1, p2)
        sim.setup_match() # Tick 0
        
        sim.resources['p1'] = 50
        sim.request_unit('p1', 'marine') # Build time = 24
        
        initial_count = len(sim.entities)
        
        # Run for 23 ticks - unit should NOT be spawned yet
        for _ in range(23):
            for ent in list(sim.entities.values()):
                ent.update(sim)
        
        self.assertEqual(len(sim.entities), initial_count)
        
        # Run 1 more tick - unit should spawn
        for ent in list(sim.entities.values()):
            ent.update(sim)
            
        self.assertEqual(len(sim.entities), initial_count + 1)
        new_unit = list(sim.entities.values())[-1]
        self.assertEqual(new_unit.type, 'marine')
        self.assertEqual(new_unit.owner_id, 'p1')

    def test_collision_repulsion(self):
        """Verify that overlapping units push each other apart"""
        u1 = Entity('worker', 'p1', 10, 10)
        u2 = Entity('worker', 'p1', 10.1, 10.1) # Extreme overlap
        
        class MockGameState:
            def __init__(self):
                self.entities = {u1.id: u1, u2.id: u2}
                self.grid = SpatialGrid(128, 128)
        
        gs = MockGameState()
        # Must populate grid manually for mock
        gs.grid.insert(u1)
        gs.grid.insert(u2)
        
        u1.update(gs)
        u2.update(gs)
        
        # Distance should increase
        dist_after = u1.pos.dist_to(u2.pos)
        self.assertGreater(dist_after, 0.14) # initial dist ~0.1414
