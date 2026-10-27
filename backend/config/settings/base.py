"""Settings shared by every environment.

Environment-specific modules import from here and override only what
differs. Secrets and deployment-specific values are never hardcoded; they come
from environment variables (see the repository's ``.env.example``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from config.env import env_int, env_list, env_str, load_env_file

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

# A local, git-ignored .env at the repository root is a development
# convenience. Real environment variables always take precedence.
load_env_file(REPO_ROOT / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False
ALLOWED_HOSTS: list[str] = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Finlume modules
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.workspaces",
    "apps.audit",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
SUPPORTED_DB_ENGINES = ("postgresql", "sqlite")
REQUIRED_POSTGRES_VARIABLES = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")


def build_databases(
    default_engine: str, engine_variable: str = "FINLUME_DB_ENGINE"
) -> dict[str, dict[str, Any]]:
    """Build ``DATABASES`` from ``engine_variable`` and the ``POSTGRES_*`` variables.

    PostgreSQL is Finlume's database. SQLite exists only as an explicit opt-in
    for a throwaway local trial and for fast isolated tests; it does not
    preserve decimal precision the way PostgreSQL ``numeric`` does and must not
    hold real financial data. There is no automatic fallback between engines.
    """
    engine = env_str(engine_variable, default=default_engine).lower()
    if engine == "postgresql":
        missing = [name for name in REQUIRED_POSTGRES_VARIABLES if not os.environ.get(name)]
        if missing:
            source = "the default" if not os.environ.get(engine_variable) else engine_variable
            raise ImproperlyConfigured(
                f"PostgreSQL is selected ({source}) but {', '.join(missing)} "
                f"{'is' if len(missing) == 1 else 'are'} not set. Copy .env.example to .env "
                "at the repository root and fill in the POSTGRES_* values "
                "(docs/development/LOCAL_SETUP.md). For a throwaway trial without "
                f"PostgreSQL, set {engine_variable}=sqlite explicitly "
                "(development and tests only)."
            )
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": env_str("POSTGRES_DB"),
                "USER": env_str("POSTGRES_USER"),
                "PASSWORD": env_str("POSTGRES_PASSWORD"),
                # 127.0.0.1, not "localhost": Windows resolves localhost to ::1 first,
                # and an IPv4-only server (such as compose.yaml's) then stalls every
                # connection until the IPv6 attempt times out.
                "HOST": env_str("POSTGRES_HOST", default="127.0.0.1"),
                "PORT": env_int("POSTGRES_PORT", default=5432),
                "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", default=60),
                "CONN_HEALTH_CHECKS": True,
                "ATOMIC_REQUESTS": True,
                "OPTIONS": {
                    "sslmode": env_str("POSTGRES_SSLMODE", default="prefer"),
                    # Fail with an error instead of hanging on an unreachable server.
                    "connect_timeout": env_int("POSTGRES_CONNECT_TIMEOUT", default=5),
                },
            }
        }
    if engine == "sqlite":
        sqlite_path = BASE_DIR / "var" / "local.sqlite3"
        sqlite_path.parent.mkdir(exist_ok=True)  # var/ is git-ignored local state
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sqlite_path,
                "ATOMIC_REQUESTS": True,
            }
        }
    raise ImproperlyConfigured(
        f"{engine_variable} must be one of {SUPPORTED_DB_ENGINES}, got {engine!r}."
    )


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# API sign-in is by email (ADR-0007). ModelBackend stays for the Django admin,
# whose login form sends a username.
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Sessions expire after this much inactivity; every request renews them.
SESSION_COOKIE_AGE = env_int("FINLUME_SESSION_AGE_SECONDS", default=8 * 60 * 60)
SESSION_SAVE_EVERY_REQUEST = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files and private document storage
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "var" / "staticfiles"

# Uploaded financial documents are never served by Django or a web server.
# There is deliberately no MEDIA_URL route; see
# docs/architecture/SECURITY_AND_PRIVACY.md.
PRIVATE_STORAGE_ROOT = Path(
    env_str("FINLUME_PRIVATE_STORAGE_ROOT", default=str(BASE_DIR / "var" / "private"))
)

STORAGES: dict[str, dict[str, Any]] = {
    # "default" is private too, so a FileField that forgets to name a storage
    # can never land somewhere publicly served.
    "default": {
        "BACKEND": "infrastructure.storage.private.PrivateFileSystemStorage",
        "OPTIONS": {"location": PRIVATE_STORAGE_ROOT},
    },
    "private_documents": {
        "BACKEND": "infrastructure.storage.private.PrivateFileSystemStorage",
        "OPTIONS": {"location": PRIVATE_STORAGE_ROOT},
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Caps request bodies and non-file form fields. It does NOT cap uploaded files:
# Django exempts file parts from this limit, and FILE_UPLOAD_MAX_MEMORY_SIZE is
# only the threshold above which an upload spools to a temporary file. Upload
# endpoints must enforce their own per-file maximum (and the reverse proxy a
# body limit) when file ingestion arrives; see docs/architecture/FOUNDATION_AUDIT.md.
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("FINLUME_MAX_REQUEST_BYTES", default=5 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

# ---------------------------------------------------------------------------
# Security headers shared by all environments
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS: list[str] = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

ADMIN_URL_PATH = env_str("FINLUME_ADMIN_URL_PATH", default="admin/")

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "ALLOWED_VERSIONS": ["v1"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Answers 401 with a Session challenge instead of DRF's 403 (ADR-0007).
        "apps.accounts.api.authentication.SessionAuthentication",
    ],
    # Secure by default: every endpoint requires authentication unless it
    # explicitly opts out (as the health endpoint does).
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "api.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("FINLUME_THROTTLE_ANON", default="60/minute"),
        "user": env_str("FINLUME_THROTTLE_USER", default="1000/hour"),
        # Sign-in attempts, per client IP and per submitted email (ADR-0007).
        "login_ip": env_str("FINLUME_THROTTLE_LOGIN_IP", default="5/minute"),
        "login_email": env_str("FINLUME_THROTTLE_LOGIN_EMAIL", default="5/minute"),
        # Adding organization members by email, per user (tenancy plan §5).
        "organization_member_add": env_str(
            "FINLUME_THROTTLE_ORGANIZATION_MEMBER_ADD", default="30/hour"
        ),
    },
    "EXCEPTION_HANDLER": "api.exceptions.api_exception_handler",
    # Monetary values travel as strings so no client parses them as floats.
    "COERCE_DECIMAL_TO_STRING": True,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = env_str("FINLUME_LOG_LEVEL", default="INFO").upper()

LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIDFilter"},
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # SQL logging can include financial values; never enable it by default.
        "django.db.backends": {"level": "WARNING", "propagate": True},
    },
}
