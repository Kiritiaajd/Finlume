"""Analysis run endpoints (MVP step 5a). Runs are created and read, never changed."""

from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from api.idempotency import IDEMPOTENCY_KEY, idempotency_key
from api.pagination import paginated_response
from api.schema import paginated
from api.users import request_user
from apps.analysis.models import AnalysisRun, AnalysisRunInputFact, with_superseded_flag
from apps.financial_records.models import ReportingEntity
from apps.workspaces.api.scoping import WorkspaceScopedView
from domain.financial_statements import PeriodType, ReportingPeriod
from services.statement_analysis import run_analysis

from .serializers import (
    AnalysisRequestSerializer,
    RunDetailSerializer,
    RunSummarySerializer,
    run_detail,
    run_summary,
)


class EntityAnalysisListView(WorkspaceScopedView):
    """An entity's runs, latest first; run a new analysis for a period."""

    @extend_schema(responses=paginated(RunSummarySerializer, "AnalysisRun"))
    def get(self, request: Request, version: str, workspace_id: UUID, entity_id: UUID) -> Response:
        entity = get_object_or_404(self.scoped(ReportingEntity.objects.all()), public_id=entity_id)
        runs = _runs(self).filter(entity=entity).order_by("-created_at", "-pk")
        return paginated_response(request, self, runs, run_summary)

    @extend_schema(
        request=AnalysisRequestSerializer,
        responses={201: RunDetailSerializer},
        parameters=[IDEMPOTENCY_KEY],
    )
    def post(self, request: Request, version: str, workspace_id: UUID, entity_id: UUID) -> Response:
        entity = get_object_or_404(self.scoped(ReportingEntity.objects.all()), public_id=entity_id)
        serializer = AnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        run = run_analysis(
            actor=request_user(request),
            workspace=self.workspace,
            entity=entity,
            period=ReportingPeriod(
                data["period_start"], data["period_end"], PeriodType(data["period_type"])
            ),
            idempotency_key=idempotency_key(request),
        )
        return Response(_detail(self, run.public_id), status=status.HTTP_201_CREATED)


class AnalysisDetailView(WorkspaceScopedView):
    @extend_schema(responses=RunDetailSerializer)
    def get(self, request: Request, version: str, workspace_id: UUID, run_id: UUID) -> Response:
        return Response(_detail(self, run_id))


def _runs(view: WorkspaceScopedView) -> QuerySet[AnalysisRun]:
    return with_superseded_flag(view.scoped(AnalysisRun.objects.all()).select_related("entity"))


def _detail(view: WorkspaceScopedView, run_id: UUID) -> dict[str, object]:
    run = get_object_or_404(_runs(view), public_id=run_id)
    inputs = (
        AnalysisRunInputFact.objects.filter(run=run)
        .select_related("fact__derived_from", "fact__statement", "fact__statement__source_document")
        .order_by("fact__line_item")
    )
    return run_detail(
        run,
        metrics=list(run.metrics.order_by("position")),
        issues=list(run.issues.order_by("position")),
        inputs=list(inputs),
    )
