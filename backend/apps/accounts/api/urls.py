from django.urls import URLPattern, URLResolver, path

from .views import CsrfView, LoginView, LogoutView, MeView, RegisterView

app_name = "accounts"

urlpatterns: list[URLPattern | URLResolver] = [
    path("auth/csrf/", CsrfView.as_view(), name="csrf"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
