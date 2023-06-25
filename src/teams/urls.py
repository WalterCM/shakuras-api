from django.urls import path

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


app_name = 'teams'

urlpatterns = [
    path('list/', views.ManageTeamView.as_view(), name='list')
]
