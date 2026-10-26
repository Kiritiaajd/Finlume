"""URL routes for version 1 of the Finlume API, mounted at ``/api/v1/``.

Each Django app contributes its own ``urls`` module; this file only composes
them so the full v1 surface is visible in one place.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
]
