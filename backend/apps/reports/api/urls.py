from django.urls import URLPattern, URLResolver, path

from .views import ReportDetailView, ReportListView

app_name = "reports"

_WS = "workspaces/<uuid:workspace_id>"

urlpatterns: list[URLPattern | URLResolver] = [
    path(f"{_WS}/reports/", ReportListView.as_view(), name="reports"),
    path(f"{_WS}/reports/<uuid:report_id>/", ReportDetailView.as_view(), name="report"),
]
