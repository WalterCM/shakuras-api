from django.urls import path, include
from rest_framework.routers import DefaultRouter
from matches import views

router = DefaultRouter()
router.register('', views.MatchViewSet)

app_name = 'matches'

urlpatterns = [
    path('editor/', views.MapEditorView.as_view(), name='map-editor'),
    path('editor/save/', views.save_map_view, name='save-map'),
    path('editor/maps/', views.list_maps_api, name='list-maps'),
    path('editor/load/', views.load_map_api, name='load-map'),
    path('editor/reference/upload/', views.upload_reference_api, name='upload-reference'),
    path('editor/reference/', views.serve_reference_api, name='serve-reference'),
    path('scenarios/', views.ScenarioVisualizerView.as_view(), name='scenario-visualizer'),
    path('scenarios/list/', views.list_scenarios_api, name='scenario-list'),
    path('scenarios/run/', views.run_scenario_api, name='scenario-run'),
    path('scenarios/upload/', views.run_scenario_upload_api, name='scenario-upload'),
    path('<int:pk>/visualize/', views.ReplayView.as_view(), name='visualizer'),
    path('', include(router.urls)),
]
