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
    """Tests the user API (public)"""

    def setUp(self):
        self.client = APIClient()
        self.payload = get_user_model().objects.get_test_payload()

    def test_create_valid_user_successful(self):
        """Tests a valid user can be created"""
        payload = self.payload.copy()
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(id=res.data.get('id'))
        self.assertTrue(user.check_password(self.payload.get('password')))
        self.assertNotIn('password', res.data)

    def test_user_exists(self):
        """Tests that an existing user can't be created again"""
        create_user(**self.payload)

        res = self.client.post(CREATE_USER_URL, self.payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        """Tests passwords should be at least 6 characters"""
        payload = self.payload.copy()
        payload['password'] = '123'

        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        user_exists = get_user_model().objects.filter(
            email=payload.get('email')
        )
        self.assertFalse(user_exists)

    def test_retrieve_user_unauthorized(self):
        """Tests authentication is required"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTests(TestCase):
    """Tests the user API (private)"""

    def setUp(self):
        self.user = create_user(**get_user_model().objects.get_test_payload())

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_successful(self):
        """Tests a user can obtain their own information"""
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_post_me_not_allowed(self):
        """Tests the post method can't be used"""
        res = self.client.post(ME_URL, {})

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
