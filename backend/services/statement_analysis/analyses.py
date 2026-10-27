"""Run and save an analysis (MVP step 5a, FR-030 to FR-034).

Inputs are assembled by rule A2; the domain engine computes; the run, every
metric, every issue and the exact facts used are saved together. A run is
never changed afterwards, so it reloads with identical values. Running again
on unchanged inputs gives a new run with the same fingerprint and values.

Inputs that cannot be assembled (no validated statement for the period, or
mixed currencies) are refused with ``ConflictError`` and nothing is saved.
"""

from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.analysis.models import AnalysisIssue, AnalysisRun, AnalysisRunInputFact, MetricResult
from apps.audit.models import AuditEvent
from apps.financial_records.models import ReportingEntity
from apps.workspaces.models import Workspace
from domain.calculations import fingerprint, run_statement_analysis
from domain.financial_statements import ReportingPeriod
from domain.validation import Issue
from services.errors import ConflictError

from .assembly import assemble_analysis_input


@transaction.atomic
def run_analysis(
    *,
    actor: User,
    workspace: Workspace,
    entity: ReportingEntity,
    period: ReportingPeriod,
    idempotency_key: UUID | None = None,
) -> AnalysisRun:
    """A new, immutable run for ``entity`` and ``period``.

    Repeating a request with the same ``idempotency_key`` returns the original
    run; the same key for another entity or period is a ``ConflictError``.
    """
    if idempotency_key is not None:
        earlier = AnalysisRun.objects.filter(
            workspace=workspace, created_by=actor, idempotency_key=idempotency_key
        ).first()
        if earlier is not None:
            return _replay(earlier, entity=entity, period=period)

    assembled = assemble_analysis_input(entity=entity, period=period)
    outcome = run_statement_analysis(assembled.facts)
    try:
        with transaction.atomic():
            run = AnalysisRun.objects.create(
                workspace=workspace,
                entity=entity,
                period_start=period.start,
                period_end=period.end,
                period_type=period.period_type.value,
                currency=outcome.currency.code,
                engine_version=outcome.engine_version,
                input_fingerprint=fingerprint(assembled.facts),
                created_by=actor,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:  # the same key, sent twice at the same moment
        raise ConflictError("A request with this Idempotency-Key is already in progress.") from None

    AnalysisRunInputFact.objects.bulk_create(
        AnalysisRunInputFact(run=run, fact=fact) for fact in assembled.source_facts
    )
    MetricResult.objects.bulk_create(
        MetricResult(
            run=run,
            position=position,
            metric_code=metric.code,
            value=metric.value,
            unit=metric.unit.value,
            methodology=metric.methodology,
            inputs={item.value: format(value, "f") for item, value in metric.inputs.items()},
        )
        for position, metric in enumerate(outcome.metrics)
    )
    issues: list[tuple[str, Issue]] = [("", issue) for issue in outcome.validation_issues]
    issues += [(metric.code, issue) for metric in outcome.metrics for issue in metric.issues]
    AnalysisIssue.objects.bulk_create(
        AnalysisIssue(
            run=run,
            position=position,
            metric_code=metric_code,
            code=issue.code.value,
            severity=issue.severity.value,
            message=issue.message,
            line_items=[item.value for item in issue.line_items],
        )
        for position, (metric_code, issue) in enumerate(issues)
    )
    # Counts and versions only: audit events never hold financial values.
    AuditEvent.record(
        "analysis.run",
        actor=actor,
        workspace=workspace,
        target=run,
        engine_version=run.engine_version,
        facts=len(assembled.source_facts),
        issues=len(issues),
    )
    return run


def _replay(run: AnalysisRun, *, entity: ReportingEntity, period: ReportingPeriod) -> AnalysisRun:
    same = (
        run.entity_id == entity.pk
        and run.period_start == period.start
        and run.period_end == period.end
        and run.period_type == period.period_type.value
    )
    if not same:
        raise ConflictError("This Idempotency-Key was already used for another analysis.")
    return run
