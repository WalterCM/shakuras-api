from django.test import TestCase
from django.contrib.auth import get_user_model

from faker import Faker

from core.models import Player


def get_test_user(nickname=None):
    fake = Faker()
    payload = {
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'nickname': nickname or fake.word(),
        'email': fake.ascii_email()
    }
    user = get_user_model()(**payload)

    return user


def get_test_player(nickname=None):
    return Player.objects.generate_player(nickname)


class UserModelTests(TestCase):

    def test_create_user_with_email_successful(self):
        """Testea creando un usuario con email"""
        nickname = 'Test'
        email = 'test@mail.com'
        password = '123456'
        user = get_user_model().objects.create_user(
            nickname=nickname,
            email=email,
            password=password
        )

        self.assertEqual(user.nickname, nickname)
        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalize(self):
        """Testea que el email de un usuario sea normalizado"""
        email = 'test@MAIL.COM'
        user = get_user_model().objects.create_user(
            nickname='Test',
            email=email,
            password='123456'
        )

        self.assertEqual(user.email, email.lower())

    def test_new_user_invalid_email(self):
        """Testea creando un nuevo usuario sin email"""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user(None, 'test123')

    def test_create_new_superuser(self):
        """Testea creando un nuevo superusuario"""
        user = get_user_model().objects.create_superuser(
            'test@mail.com',
            'test123',
            nickname='Test'
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
