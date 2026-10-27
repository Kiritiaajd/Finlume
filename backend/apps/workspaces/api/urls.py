from django.urls import URLPattern, URLResolver, path

from .views import MemberDetailView, MemberListView, WorkspaceDetailView, WorkspaceListView

app_name = "workspaces"

urlpatterns: list[URLPattern | URLResolver] = [
    path("workspaces/", WorkspaceListView.as_view(), name="list"),
    path("workspaces/<uuid:workspace_id>/", WorkspaceDetailView.as_view(), name="detail"),
    path("workspaces/<uuid:workspace_id>/members/", MemberListView.as_view(), name="members"),
    path(
        "workspaces/<uuid:workspace_id>/members/<uuid:user_id>/",
        MemberDetailView.as_view(),
        name="member",
    ),
]
