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
from apps.financial_records.models import FinancialStatement, ReportingEntity, StatementStatus
from apps.workspaces.api.scoping import WorkspaceScopedView
from domain.financial_statements import LineItem
from services.statement_analysis import (
    create_entity,
    create_statement,
    restate_statement,
    update_draft,
    validate_statement,
)

from .serializers import (
    EntityInputSerializer,
    RestatementInputSerializer,
    StatementInputSerializer,
    entity_data,
    fact_data,
    issue_data,
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
    """One statement version with its raw rows (and facts, once validated); edit a draft."""

    def get(
        self, request: Request, version: str, workspace_id: UUID, statement_id: UUID
    ) -> Response:
        return Response(_statement_with_rows(_statement(self, statement_id)))

    def patch(
        self, request: Request, version: str, workspace_id: UUID, statement_id: UUID
    ) -> Response:
        statement = _statement(self, statement_id)
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
        return Response(_statement_with_rows(_statement(self, updated.public_id)))


class StatementValidateView(WorkspaceScopedView):
    """Draft → validated: saves the facts and returns consistency warnings, never blocking."""

    def post(
        self, request: Request, version: str, workspace_id: UUID, statement_id: UUID
    ) -> Response:
        outcome = validate_statement(
            actor=request_user(request),
            workspace=self.workspace,
            statement=_statement(self, statement_id),
        )
        data = _statement_with_rows(_statement(self, outcome.statement.public_id))
        return Response({**data, "issues": [issue_data(issue) for issue in outcome.issues]})


class StatementRestatementView(WorkspaceScopedView):
    """Start the next version of a validated statement, as a draft."""

    def post(
        self, request: Request, version: str, workspace_id: UUID, statement_id: UUID
    ) -> Response:
        statement = _statement(self, statement_id)
        serializer = RestatementInputSerializer(data=request.data, context={"statement": statement})
        serializer.is_valid(raise_exception=True)
        draft = restate_statement(
            actor=request_user(request),
            workspace=self.workspace,
            statement=statement,
            reason=serializer.validated_data["reason"],
            rows=serializer.validated_data.get("line_items"),
        )
        return Response(
            _statement_with_rows(_statement(self, draft.public_id)),
            status=status.HTTP_201_CREATED,
        )


class LineItemTaxonomyView(APIView):
    """The canonical line items with their definitions: help text for entry forms.

    Reference data, the same for everyone, so it is one complete page.
    """

    def get(self, request: Request, version: str) -> Response:
        items = [taxonomy_data(item) for item in LineItem]
        return Response({"count": len(items), "next": None, "previous": None, "results": items})


def _statement(view: WorkspaceScopedView, statement_id: UUID) -> FinancialStatement:
    return get_object_or_404(
        view.scoped(FinancialStatement.objects.all()).select_related("entity", "supersedes"),
        public_id=statement_id,
    )


def _statement_with_rows(statement: FinancialStatement) -> dict[str, Any]:
    """The statement, its raw rows and, unless it is a draft, its facts in base units."""
    rows = statement.line_items.order_by("row_number")
    facts = (
        []
        if statement.status == StatementStatus.DRAFT
        else statement.facts.select_related("derived_from").order_by("derived_from__row_number")
    )
    return {
        **statement_data(statement),
        "line_items": [line_item_data(row) for row in rows],
        "facts": [fact_data(fact) for fact in facts],
    }
