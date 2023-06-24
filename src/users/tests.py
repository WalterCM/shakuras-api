from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status


CREATE_USER_URL = reverse('users:create')
ME_URL = reverse('users:me')


def create_user(**params):
    return get_user_model().objects.create_user(**params)


class PublicTests(TestCase):
    """Testea el API de usuarios (publico)"""
    payload = {
        'email': 'test@mail.com',
        'password': '123456',
        'name': 'Bob Ross',
    }

    def setUp(self):
        self.client = APIClient()

    def test_create_valid_user_successful(self):
        """Testea que se pueda crear un usuario valido"""
        payload = self.payload.copy()
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(id=res.data.get('id'))
        self.assertTrue(user.check_password(self.payload.get('password')))
        self.assertNotIn('password', res.data)

    def test_user_exists(self):
        """Testea que no se pueda crear un usuario que ya existe"""
        create_user(**self.payload)

        res = self.client.post(CREATE_USER_URL, self.payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        """Testea que el pass deberia ser al menos 6 caracteres"""
        payload = self.payload.copy()
        payload['password'] = '123'

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        user_exists = get_user_model().objects.filter(
            email=payload.get('email')
        )
        self.assertFalse(user_exists)

    def test_retrieve_user_unauthorized(self):
        """Testea que la autenticacion es requerida"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class PrivateTests(TestCase):
    """Testea el API de usuarios (privado)"""

    def setUp(self):
        self.user = create_user(
            email='test@mail.com',
            password='123456'
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_successful(self):
        """Testea que un usuario pueda obtener su propia informacion"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_post_me_not_allowed(self):
        """Testea que no se pueda usar el metodo post"""
        res = self.client.post(ME_URL, {})

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
