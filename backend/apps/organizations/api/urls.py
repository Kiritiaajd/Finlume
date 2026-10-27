from django.urls import URLPattern, URLResolver, path

from .views import MemberDetailView, MemberListView, OrganizationDetailView, OrganizationListView

app_name = "organizations"

urlpatterns: list[URLPattern | URLResolver] = [
    path("organizations/", OrganizationListView.as_view(), name="list"),
    path("organizations/<uuid:organization_id>/", OrganizationDetailView.as_view(), name="detail"),
    path(
        "organizations/<uuid:organization_id>/members/",
        MemberListView.as_view(),
        name="members",
    ),
    path(
        "organizations/<uuid:organization_id>/members/<uuid:user_id>/",
        MemberDetailView.as_view(),
        name="member",
    ),
]
