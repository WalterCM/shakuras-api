from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from core.models import Player
from core.tests import get_test_user

LIST_PLAYERS_URL = reverse('players:player-list')


def create_player(**params):
    return Player.objects.create(**params)


def get_player_detail_url(nickname):
    return reverse('players:player-detail', kwargs={'nickname': nickname})


def get_player_update_url(nickname):
    return reverse('players:player-update', kwargs={'nickname': nickname})


class PublicTests(TestCase):
    """Tests the players API (public)"""

    def setUp(self):
        self.client = APIClient()
        self.payload = get_user_model().objects.get_test_payload()

    # def test_create_valid_player_successful(self):
    #     """Testea que se pueda crear un usuario valido"""
    #     payload = self.payload.copy()
    #     res = self.client.post(CREATE_PLAYER_URL, payload)
    #
    #     self.assertEqual(res.status_code, status.HTTP_201_CREATED)
    #     player = Player.objects.get(id=res.data.get('id'))
    #     self.assertTrue(self.payload.get('first_name'), player.first_name)
    #     self.assertTrue(self.payload.get('last_name'), player.last_name)
    #     self.assertTrue(self.payload.get('nickname'), player.nickname)

    def test_create_player_unauthorized(self):
        """Testes authentication is required for getting player creation"""
        res = self.client.post(LIST_PLAYERS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_player_list_unauthorized(self):
        """Testes authentication is required for getting player list"""
        res = self.client.get(LIST_PLAYERS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTests(TestCase):
    """Tests the players API (private)"""

    def setUp(self):
        payload = {
            'first_name': 'Bob',
            'last_name': 'Ross',
            'nickname': 'Test',
            'country': 'Peru'
        }
        self.user = get_test_user()
        self.player = create_player(**payload)
        self.player.save()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_player_profile_successful(self):
        """Tests a user can see a public player profile"""
        res = self.client.get(get_player_detail_url(self.player.nickname))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
