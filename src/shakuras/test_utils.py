from faker import Faker
from django.contrib.auth import get_user_model
from players.models import Player

def get_test_user(nickname=None):
    fake = Faker()
    payload = {
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'nickname': nickname or fake.word(),
        'email': fake.ascii_email()
    }
    User = get_user_model()
    # We use a default password for test users to stay consistent
    user = User.objects.create_user(**payload, password='testpassword123')
    return user

def get_test_player(nickname=None):
    return Player.objects.generate_player(nickname)
