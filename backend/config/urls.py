"""Root URL configuration.

All client-facing endpoints live under ``/api/<version>/``. Only ``v1``
exists; a future ``v2`` gets its own URL module and both are served side by
side during a documented deprecation window (docs/api/API_CONVENTIONS.md).
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

urlpatterns = [
    re_path(r"^api/(?P<version>v1)/", include("config.api_v1")),
    path(settings.ADMIN_URL_PATH, admin.site.urls),
]

# The backend is API-first: unknown URLs and server errors answer with the
# same JSON error envelope as API errors instead of HTML pages.
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
