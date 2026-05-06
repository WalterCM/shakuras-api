import pytest
from django.urls import reverse
from matches.engine import MatchSimulator, Map as EngineMap
from players.models import Player
from matches.loader import MAPS_DIR
import yaml
from pathlib import Path


@pytest.mark.django_db
class TestMapEditor:
    @pytest.fixture
    def player_factory(self):
        def _create_player(nickname="Flash"):
            return Player.objects.create(nickname=nickname)
        return _create_player

    def test_editor_page_renders(self, client):
        """Test that the map editor page renders correctly"""
        url = reverse('matches:editor')
        response = client.get(url)
        assert response.status_code == 200
        assert b"Shakuras Editor" in response.content

    def test_save_map_api(self, client):
        """Test the save_map_view API endpoint creates a YAML file"""
        url = reverse('matches:editor-save')
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
        # Verify file was created
        map_path = MAPS_DIR / 'api_map.yaml'
        assert map_path.exists()
        # Cleanup
        if map_path.exists():
            map_path.unlink()

    def test_simulator_with_engine_map(self, player_factory):
        """Test that MatchSimulator correctly uses EngineMap data"""
        p1 = player_factory("P1")
        p2 = player_factory("P2")
        
        from matches.utils import Vector2D
        engine_map = EngineMap(
            name="Sim Map",
            width=200,
            height=200,
            spawn_points={
                'p1': Vector2D(10, 10),
                'p2': Vector2D(190, 190)
            },
            minerals=[{'x': 100, 'y': 100}]
        )
        
        sim = MatchSimulator(p1, p2, map_instance=engine_map, max_ticks=10)
        sim.setup_match()
        history = sim.simulate()
        
        # Verify map dimensions and tick 0 entities
        tick0 = history[0]
        assert tick0['map']['width'] == 200
        
        # Should have 2 bases, 8 scvs (4 per base), 1 mineral patch = 11 entities
        assert len(tick0['entities']) == 11
        
        # Check base positions (now centered: 10+2, 10+1.5)
        bases = [e for e in tick0['entities'] if e['type'] == 'base']
        assert any(b['x'] == 12 and b['y'] == 11.5 for b in bases)
        assert any(b['x'] == 192 and b['y'] == 191.5 for b in bases)
