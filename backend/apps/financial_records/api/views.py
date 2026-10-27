"""Entity, statement and line-item taxonomy endpoints.

Every entity and statement lookup goes through ``WorkspaceScopedView.scoped``,
so an ID from another workspace is simply not found (``404``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.pagination import paginated_response
from api.users import request_user
from apps.financial_records.models import FinancialStatement, ReportingEntity
from apps.workspaces.api.scoping import WorkspaceScopedView
from domain.financial_statements import LineItem
from services.statement_analysis import create_entity, create_statement, update_draft

from .serializers import (
    EntityInputSerializer,
    StatementInputSerializer,
    entity_data,
    line_item_data,
    statement_data,
    taxonomy_data,
)


class EntityListView(WorkspaceScopedView):
    def get(self, request: Request, version: str, workspace_id: UUID) -> Response:
        entities = self.scoped(ReportingEntity.objects.all()).order_by("name", "pk")
        return paginated_response(request, self, entities, entity_data)

    def post(self, request: Request, version: str, workspace_id: UUID) -> Response:
        serializer = EntityInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entity = create_entity(
            actor=request_user(request), workspace=self.workspace, **serializer.validated_data
        )
        return Response(entity_data(entity), status=status.HTTP_201_CREATED)


class EntityDetailView(WorkspaceScopedView):
    def get(self, request: Request, version: str, workspace_id: UUID, entity_id: UUID) -> Response:
        entity = get_object_or_404(self.scoped(ReportingEntity.objects.all()), public_id=entity_id)
        return Response(entity_data(entity))


class EntityStatementListView(WorkspaceScopedView):
    """Every version of every statement of one entity; create a draft."""

    def get(self, request: Request, version: str, workspace_id: UUID, entity_id: UUID) -> Response:
        entity = get_object_or_404(self.scoped(ReportingEntity.objects.all()), public_id=entity_id)
        statements = (
            self.scoped(FinancialStatement.objects.all())
            .filter(entity=entity)
            .select_related("entity", "supersedes")
            .order_by("-period_end", "statement_type", "-version", "pk")
        )
        return paginated_response(request, self, statements, statement_data)

    def post(self, request: Request, version: str, workspace_id: UUID, entity_id: UUID) -> Response:
        entity = get_object_or_404(self.scoped(ReportingEntity.objects.all()), public_id=entity_id)
        serializer = StatementInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        statement = create_statement(
            actor=request_user(request),
            workspace=self.workspace,
            entity=entity,
            rows=fields.pop("line_items"),
            **fields,
        )
        return Response(_statement_with_rows(statement), status=status.HTTP_201_CREATED)


class StatementDetailView(WorkspaceScopedView):
    """One statement version with its raw rows; edit it while it is a draft."""

    def get(
        self, request: Request, version: str, workspace_id: UUID, statement_id: UUID
    ) -> Response:
        return Response(_statement_with_rows(self._statement(statement_id)))

    def patch(
        self, request: Request, version: str, workspace_id: UUID, statement_id: UUID
    ) -> Response:
        statement = self._statement(statement_id)
        serializer = StatementInputSerializer(
            data=request.data, partial=True, context={"statement": statement}
        )
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        updated = update_draft(
            actor=request_user(request),
            workspace=self.workspace,
            statement=statement,
            rows=changes.pop("line_items", None),
            **changes,
        )
        return Response(_statement_with_rows(self._statement(updated.public_id)))

    def _statement(self, statement_id: UUID) -> FinancialStatement:
        return get_object_or_404(
            self.scoped(FinancialStatement.objects.all()).select_related("entity", "supersedes"),
            public_id=statement_id,
        )


class LineItemTaxonomyView(APIView):
    """The canonical line items with their definitions: help text for entry forms.

    Reference data, the same for everyone, so it is one complete page.
    """

    def get(self, request: Request, version: str) -> Response:
        items = [taxonomy_data(item) for item in LineItem]
        return Response({"count": len(items), "next": None, "previous": None, "results": items})


def _statement_with_rows(statement: FinancialStatement) -> dict[str, Any]:
    rows = statement.line_items.order_by("row_number")
    return {**statement_data(statement), "line_items": [line_item_data(row) for row in rows]}
