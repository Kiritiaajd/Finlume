"""Settings for any deployed instance, including self-hosted installs.

Every value that differs between deployments is required from the
environment; startup fails rather than running with an unsafe default.
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int, env_list, env_str

from .base import *  # noqa: F403
from .base import build_databases

DEBUG = False

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters long.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list the host names this instance serves."
    )

DATABASES = build_databases(default_engine="postgresql")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production deployments must use PostgreSQL.")

# HTTPS. Self-hosters behind a TLS-terminating reverse proxy set
# FINLUME_TRUST_PROXY_SSL_HEADER=true; never enable it without such a proxy.
SECURE_SSL_REDIRECT = env_bool("FINLUME_SECURE_SSL_REDIRECT", default=True)
if env_bool("FINLUME_TRUST_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env_int("FINLUME_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("FINLUME_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env_bool("FINLUME_HSTS_PRELOAD", default=False)

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
