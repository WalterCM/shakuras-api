from django.test import TestCase, RequestFactory
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from core.models import Match, MatchParticipant, Player, Team, Replay
from matches.serializers import MatchSerializer
from matches.engine import Entity, MatchSimulator
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
        self.assertEqual(entity.status, 'idle')

    def test_entity_take_damage(self):
        """Verify HP reduction and 'dead' status"""
        entity = Entity('marine', 'p1', 10, 10)
        initial_hp = entity.hp
        
        entity.take_damage(10)
        self.assertEqual(entity.hp, initial_hp - 10)
        self.assertNotEqual(entity.status, 'dead')
        
        entity.take_damage(initial_hp)
        self.assertEqual(entity.hp, 0)
        self.assertEqual(entity.status, 'dead')

    def test_entity_movement(self):
        """Verify pos_x/y updates correctly in 'move' state"""
        entity = Entity('marine', 'p1', 0, 0)
        entity.status = 'move'
        entity.destination = (10, 0)
        
        # One update tick
        entity.update(None)
        
        self.assertGreater(entity.pos_x, 0)
        self.assertEqual(entity.pos_y, 0)
        self.assertLess(entity.pos_x, 10)
        
        # Many ticks to reach destination
        for _ in range(20):
            entity.update(None)
            
        self.assertEqual(entity.pos_x, 10)
        self.assertEqual(entity.pos_y, 0)
        self.assertEqual(entity.status, 'idle')

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
        
        game_state = MockGameState()
        attacker.status = 'attack'
        attacker.target_id = target.id
        
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
        history = sim.simulate()
        
        # Tick 0 should have full snapshots
        self.assertEqual(history[0]['tick'], 0)
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
        
        worker = Entity('worker', player1.id, 0, 0)
        patch = Entity('mineral_patch', 'neutral', 5, 0) # Close to worker
        base = Entity('base', player1.id, 10, 0)
        
        class MockGameState:
            def __init__(self, resources):
                self.entities = {patch.id: patch, worker.id: worker, base.id: base}
                self.resources = resources
            def add_minerals(self, pid, amount):
                self.resources[pid] += amount
                
        resources = {player1.id: 50.0}
        gs = MockGameState(resources)
        
        worker.status = 'harvest'
        worker.target_id = patch.id
        
        # 1. Harvest trip
        worker.update(gs) # Move to patch or arrive
        # If speed is high enough, it might arrive. Let's assume it mines.
        while worker.status == 'harvest':
            worker.update(gs)
            
        # Should now be carrying minerals and in 'return' state
        self.assertEqual(worker.carrying, worker.harvest_amount)
        self.assertEqual(worker.status, 'return')
        self.assertEqual(resources[player1.id], 50.0) # Not deposited yet!

        # 2. Return trip
        while worker.status == 'return':
            worker.update(gs)
            
        # Should have deposited
        self.assertEqual(resources[player1.id], 50.0 + worker.harvest_amount)
        self.assertEqual(worker.carrying, 0)
        self.assertEqual(worker.status, 'harvest')

    def test_interrupted_trip(self):
        """Verify that killing a worker carrying minerals drops them"""
        worker = Entity('worker', 'p1', 0, 0)
        worker.carrying = 8
        worker.status = 'return'
        
        worker.take_damage(40) # Death
        self.assertEqual(worker.status, 'dead')
        self.assertEqual(worker.carrying, 0)
