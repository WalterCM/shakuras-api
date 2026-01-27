from django.urls import path, include
from rest_framework.routers import DefaultRouter
from matches import views

router = DefaultRouter()
router.register('', views.MatchViewSet)

app_name = 'matches'

urlpatterns = [
    path('', include(router.urls)),
    path('<int:pk>/visualize/', views.ReplayView.as_view(), name='visualizer'),
]
