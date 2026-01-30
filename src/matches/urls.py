from django.urls import path, include
from rest_framework.routers import DefaultRouter
from matches import views

router = DefaultRouter()
router.register('', views.MatchViewSet)

app_name = 'matches'

urlpatterns = [
    path('editor/', views.MapEditorView.as_view(), name='map-editor'),
    path('editor/save/', views.save_map_view, name='save-map'),
    path('<int:pk>/visualize/', views.ReplayView.as_view(), name='visualizer'),
    path('', include(router.urls)),
]
