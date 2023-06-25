from django.urls import path, include

from rest_framework.routers import DefaultRouter

from . import views

app_name = 'players'

router = DefaultRouter()


router.register('', views.PlayerViewSet)

urlpatterns = [
    path('', include(router.urls))
]
