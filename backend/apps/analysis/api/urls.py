from django.urls import URLPattern, URLResolver, path

from .views import AnalysisDetailView, EntityAnalysisListView

app_name = "analysis"

_WS = "workspaces/<uuid:workspace_id>"

urlpatterns: list[URLPattern | URLResolver] = [
    path(
        f"{_WS}/entities/<uuid:entity_id>/analyses/",
        EntityAnalysisListView.as_view(),
        name="entity-analyses",
    ),
    path(f"{_WS}/analyses/<uuid:run_id>/", AnalysisDetailView.as_view(), name="analysis"),
]
