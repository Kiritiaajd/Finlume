from django.urls import URLPattern, URLResolver, path

from .views import (
    EntityDetailView,
    EntityListView,
    EntityStatementListView,
    LineItemTaxonomyView,
    StatementDetailView,
)

app_name = "financial_records"

_WS = "workspaces/<uuid:workspace_id>"

urlpatterns: list[URLPattern | URLResolver] = [
    path("line-items/", LineItemTaxonomyView.as_view(), name="line-items"),
    path(f"{_WS}/entities/", EntityListView.as_view(), name="entities"),
    path(f"{_WS}/entities/<uuid:entity_id>/", EntityDetailView.as_view(), name="entity"),
    path(
        f"{_WS}/entities/<uuid:entity_id>/statements/",
        EntityStatementListView.as_view(),
        name="entity-statements",
    ),
    path(
        f"{_WS}/statements/<uuid:statement_id>/",
        StatementDetailView.as_view(),
        name="statement",
    ),
]
