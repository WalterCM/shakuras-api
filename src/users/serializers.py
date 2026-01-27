from django.contrib.auth import get_user_model

from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user model"""

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'nickname', 'email', 'password', 'first_name', 'last_name'
        )
        extra_kwargs = {
            'id': {'read_only': True},
            'password': {'write_only': True, 'min_length': 6}
        }

    def create(self, validated_data):
        """Creates a new user and returns it"""
        return get_user_model().objects.create_user(**validated_data)
