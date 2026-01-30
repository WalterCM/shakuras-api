import pytest
from django.urls import reverse
from matches.models import Map
from matches.engine import MatchSimulator
from players.models import Player

@pytest.mark.django_db
class TestMapEditor:
    @pytest.fixture
    def player_factory(self):
        def _create_player(nickname="Flash"):
            return Player.objects.create(nickname=nickname)
        return _create_player

    def test_editor_page_renders(self, client):
        """Test that the map editor page renders correctly"""
        url = reverse('matches:map-editor')
        response = client.get(url)
        assert response.status_code == 200
        assert b"Map Editor" in response.content

    def test_map_creation(self):
        """Test creating a Map model instance"""
        m = Map.objects.create(
            name="Test Arena",
            width=100,
            height=100,
            spawn_points={'p1': {'x': 5, 'y': 5}, 'p2': {'x': 95, 'y': 95}},
            minerals=[{'x': 50, 'y': 50}]
        )
        assert m.name == "Test Arena"
        assert m.spawn_points['p1']['x'] == 5

    def test_save_map_api(self, client):
        """Test the save_map_view API endpoint"""
        url = reverse('matches:save-map')
        payload = {
            'name': 'API Map',
            'width': 64,
            'height': 64,
            'spawn_points': {'p1': {'x': 2, 'y': 2}, 'p2': {'x': 60, 'y': 60}},
            'minerals': [{'x': 10, 'y': 10}, {'x': 20, 'y': 20}]
        }
        response = client.post(url, data=payload, content_type='application/json')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        assert Map.objects.filter(name='API Map').exists()

    def test_simulator_with_map(self, player_factory):
        """Test that MatchSimulator correctly uses Map data"""
        p1 = player_factory("P1")
        p2 = player_factory("P2")
        
        m = Map.objects.create(
            name="Sim Map",
            width=200,
            height=200,
            spawn_points={'p1': {'x': 10, 'y': 10}, 'p2': {'x': 190, 'y': 190}},
            minerals=[{'x': 100, 'y': 100}]
        )
        
        sim = MatchSimulator(p1, p2, map_instance=m, max_ticks=10)
        history = sim.simulate()
        
        # Verify map dimensions and tick 0 entities
        tick0 = history[0]
        assert tick0['map']['width'] == 200
        
        # Should have 2 bases, 8 workers (4 per base), 1 mineral patch = 11 entities
        assert len(tick0['entities']) == 11
        
        # Check base positions (now centered: 10+2, 10+1.5)
        bases = [e for e in tick0['entities'] if e['type'] == 'base']
        assert any(b['x'] == 12 and b['y'] == 11.5 for b in bases)
        assert any(b['x'] == 192 and b['y'] == 191.5 for b in bases)
