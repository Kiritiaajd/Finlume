"""Request and response shapes for authentication endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User


class CredentialsSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class RegistrationSerializer(CredentialsSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # Django's password validators (length, similarity, common, numeric).
        try:
            validate_password(attrs["password"], user=User(email=attrs["email"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from None
        return attrs


class CurrentUserSerializer(serializers.Serializer[User]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    email = serializers.EmailField(read_only=True)
    personal_workspace_id = serializers.SerializerMethodField()

    def get_personal_workspace_id(self, user: User) -> UUID | None:
        # One query. A missing reverse one-to-one raises an AttributeError subclass,
        # so getattr's default covers accounts that have not signed in yet.
        workspace = getattr(user, "personal_workspace", None)
        return workspace.public_id if workspace is not None else None
