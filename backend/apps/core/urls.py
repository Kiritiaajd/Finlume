from django.db import transaction
from django.urls import path

from .views import HealthView

app_name = "core"

urlpatterns = [
    # Outside ATOMIC_REQUESTS: opening a transaction would itself fail on a
    # database outage, turning the intended 503 into an unhandled 500.
    path("health/", transaction.non_atomic_requests(HealthView.as_view()), name="health"),
]
