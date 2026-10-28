"""Report endpoints (MVP step 5b). Viewers read; editors write."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Count, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from api.pagination import paginated_response
from api.schema import paginated
from api.users import request_user
from apps.analysis.models import AnalysisIssue, AnalysisRun, MetricResult, with_superseded_flag
from apps.reports.models import Report, ReportRun
from apps.workspaces.api.scoping import WorkspaceScopedView
from services.statement_analysis import create_report, update_report

from .serializers import (
    ReportDetailSerializer,
    ReportInputSerializer,
    ReportSummarySerializer,
    ReportUpdateSerializer,
    report_detail,
    report_summary,
)


class ReportListView(WorkspaceScopedView):
    @extend_schema(responses=paginated(ReportSummarySerializer, "Report"))
    def get(self, request: Request, version: str, workspace_id: UUID) -> Response:
        reports = (
            self.scoped(Report.objects.all())
            .annotate(run_count=Count("runs"))
            .order_by("-created_at", "-pk")
        )
        return paginated_response(request, self, reports, report_summary)

    @extend_schema(request=ReportInputSerializer, responses={201: ReportDetailSerializer})
    def post(self, request: Request, version: str, workspace_id: UUID) -> Response:
        serializer = ReportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = create_report(
            actor=request_user(request), workspace=self.workspace, **serializer.validated_data
        )
        return Response(_detail(self, report.public_id), status=status.HTTP_201_CREATED)


class ReportDetailView(WorkspaceScopedView):
    @extend_schema(responses=ReportDetailSerializer)
    def get(self, request: Request, version: str, workspace_id: UUID, report_id: UUID) -> Response:
        return Response(_detail(self, report_id))

    @extend_schema(request=ReportUpdateSerializer, responses=ReportDetailSerializer)
    def patch(
        self, request: Request, version: str, workspace_id: UUID, report_id: UUID
    ) -> Response:
        report = get_object_or_404(self.scoped(Report.objects.all()), public_id=report_id)
        serializer = ReportUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        update_report(
            actor=request_user(request),
            workspace=self.workspace,
            report=report,
            **serializer.validated_data,
        )
        return Response(_detail(self, report_id))


def _detail(view: WorkspaceScopedView, report_id: UUID) -> dict[str, Any]:
    report = get_object_or_404(view.scoped(Report.objects.all()), public_id=report_id)
    links = ReportRun.objects.filter(report=report)
    position = Subquery(links.filter(run=OuterRef("pk")).values("position")[:1])
    runs = list(
        with_superseded_flag(
            AnalysisRun.objects.filter(pk__in=links.values("run_id"))
            .select_related("entity")
            .annotate(position=position)
        ).order_by("position")
    )
    pks = [run.pk for run in runs]
    metrics = list(MetricResult.objects.filter(run_id__in=pks).order_by("run_id", "position"))
    issues = list(AnalysisIssue.objects.filter(run_id__in=pks).order_by("run_id", "position"))
    return report_detail(report, runs, metrics, issues)
