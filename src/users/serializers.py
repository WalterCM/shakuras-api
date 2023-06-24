from django.contrib.auth import get_user_model

from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer para el modelo User"""

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'email', 'password', 'name'
        )
        extra_kwargs = {
            'id': {'read_only': True},
            'name': {'required': False},
            'password': {'write_only': True, 'min_length': 6}
        }

    def create(self, validated_data):
        """Crea un nuevo usuario y lo retorna"""
        return get_user_model().objects.create_user(**validated_data)
