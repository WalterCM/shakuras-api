from django.contrib.auth import get_user_model

from engine.users.serializers import UserSerializer as BaseUserSerializer


class UserSerializer(BaseUserSerializer):
    """Serializer for user model"""

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'nickname', 'email', 'password', 'first_name', 'last_name'
        )
        extra_kwargs = {
            'id': {'read_only': True},
            'name': {'required': False},
            'password': {'write_only': True, 'min_length': 6}
        }
