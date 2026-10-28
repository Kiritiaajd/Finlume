"""Authentication endpoints: CSRF, register, login, logout and me."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.exceptions import error_body
from apps.accounts.models import User
from services.accounts import complete_sign_in, record_failed_sign_in, register_user

from .authentication import SESSION_CHALLENGE, enforce_csrf
from .serializers import CredentialsSerializer, CurrentUserSerializer, RegistrationSerializer
from .throttles import LoginEmailThrottle, LoginIPThrottle

EMAIL_BACKEND = "apps.accounts.backends.EmailBackend"


def _current_user(user: Any) -> dict[str, Any]:
    return dict(CurrentUserSerializer(user).data)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie that the client echoes in ``X-CSRFToken`` on writes."""

    permission_classes = (AllowAny,)

    @extend_schema(responses={204: None})
    def get(self, request: Request, version: str) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnonymousWriteView(APIView):
    """Base for sign-in and registration: open to anyone, but CSRF-checked."""

    permission_classes = (AllowAny,)

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        enforce_csrf(request)


class RegisterView(AnonymousWriteView):
    @extend_schema(request=RegistrationSerializer, responses={201: CurrentUserSerializer})
    def post(self, request: Request, version: str) -> Response:
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_user(**serializer.validated_data)
        login(request._request, user, backend=EMAIL_BACKEND)
        return Response(_current_user(user), status=status.HTTP_201_CREATED)


class LoginView(AnonymousWriteView):
    throttle_classes = (LoginIPThrottle, LoginEmailThrottle)

    @extend_schema(request=CredentialsSerializer, responses=CurrentUserSerializer)
    def post(self, request: Request, version: str) -> Response:
        serializer = CredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data

        user = authenticate(request._request, **credentials)
        if not isinstance(user, User):  # None: wrong email or password, or inactive
            # Returned, not raised: raising would roll back the audit event
            # together with the request transaction.
            record_failed_sign_in(credentials["email"])
            return Response(
                error_body("authentication_failed", "Email or password is incorrect."),
                status=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": SESSION_CHALLENGE},
            )

        login(request._request, user)
        complete_sign_in(user)
        return Response(_current_user(user))


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request, version: str) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=CurrentUserSerializer)
    def get(self, request: Request, version: str) -> Response:
        return Response(_current_user(request.user))
