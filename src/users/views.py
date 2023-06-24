from rest_framework import generics
from rest_framework import permissions

from users import serializers


class CreateUserView(generics.CreateAPIView):
    """Crea un nuevo usuario en el sistema"""
    serializer_class = serializers.UserSerializer


class ManageUserView(generics.RetrieveUpdateAPIView):
    """Administra el perfil de un usuario"""
    serializer_class = serializers.UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user
