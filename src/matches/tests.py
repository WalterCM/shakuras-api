from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Match, MatchParticipant, Player, Team, Replay
from matches.serializers import MatchSerializer

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
