from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


app_name = 'players'

urlpatterns = [
    path('list/', views.ManagePlayerView.as_view(), name='me')
]
