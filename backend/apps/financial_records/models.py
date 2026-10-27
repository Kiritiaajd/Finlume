"""ReportingEntity, FinancialStatement, StatementLineItem and FinancialFact.

Persistence only: the domain engine never sees these rows. Codes for
statement types, period types, scales and line items come from
``domain.financial_statements``, so the database and the engine share one
taxonomy; changing it there shows up as a pending migration.

Cross-row rules that a single-column foreign key cannot express (a statement
and its entity in the same workspace, a fact matching its statement) are
composite foreign keys on PostgreSQL, added in migrations 0002 and 0003 on
top of the ``*_key`` unique constraints declared here.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import PublicModel
from apps.documents.models import SourceDocument
from apps.workspaces.models import Workspace
from domain.financial_statements import LineItem, PeriodType, Scale, StatementType


def _choices(codes: list[str]) -> list[tuple[str, str]]:
    return [(code, code.replace("_", " ").capitalize()) for code in codes]


STATEMENT_TYPES = [t.value for t in StatementType]
PERIOD_TYPES = [p.value for p in PeriodType]
SCALES = [s.name.lower() for s in Scale]
LINE_ITEMS = [item.value for item in LineItem]

_CURRENCY_FORMAT = r"^[A-Z]{3}$"


class EntityType(models.TextChoices):
    BUSINESS = "business", "Business"
    INDIVIDUAL = "individual", "Individual"
    LISTED_COMPANY = "listed_company", "Listed company"


class StatementStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    VALIDATED = "validated", "Validated"
    SUPERSEDED = "superseded", "Superseded"


class ReviewStatus(models.TextChoices):
    UNREVIEWED = "unreviewed", "Unreviewed"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"


class ReportingEntity(PublicModel):
    """The business, person or listed company whose statements are analysed."""

    # No separate index: both unique constraints below lead with workspace.
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="reporting_entities", db_index=False
    )
    name = models.CharField(max_length=200)
    entity_type = models.CharField(max_length=16, choices=EntityType.choices)
    # Blank when none; suggested currency for new statements.
    default_currency = models.CharField(max_length=3, blank=True)
    fiscal_year_end_month = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="financial_records_reportingentity_name_unique"
            ),
            models.CheckConstraint(
                condition=Q(entity_type__in=EntityType.values),
                name="financial_records_reportingentity_entity_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(default_currency="") | Q(default_currency__regex=_CURRENCY_FORMAT),
                name="financial_records_reportingentity_currency_format",
            ),
            models.CheckConstraint(
                condition=Q(fiscal_year_end_month__isnull=True)
                | Q(fiscal_year_end_month__gte=1, fiscal_year_end_month__lte=12),
                name="financial_records_reportingentity_fiscal_month_valid",
            ),
            # Composite foreign key target: statements in the same workspace.
            models.UniqueConstraint(
                fields=["workspace", "id"], name="financial_records_reportingentity_workspace_key"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class FinancialStatement(PublicModel):
    """One statement type for one entity and one period, at one version.

    A restatement is a new version that ``supersedes`` the previous one. Per
    (entity, statement type, period) there is at most one validated version,
    which analyses use, and at most one draft, so a restatement can be
    prepared while the validated version stays in use.
    """

    # No separate index: the (workspace, entity, period_end) index leads with it.
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="financial_statements", db_index=False
    )
    # No separate index: the version key below leads with entity.
    entity = models.ForeignKey(
        ReportingEntity, on_delete=models.RESTRICT, related_name="statements", db_index=False
    )
    statement_type = models.CharField(max_length=24, choices=_choices(STATEMENT_TYPES))
    period_start = models.DateField()
    period_end = models.DateField()  # balance sheet figures are as of this date
    period_type = models.CharField(max_length=16, choices=_choices(PERIOD_TYPES))
    currency = models.CharField(max_length=3)
    reported_scale = models.CharField(max_length=16, choices=_choices(SCALES))
    source_document = models.ForeignKey(
        SourceDocument, on_delete=models.RESTRICT, related_name="statements"
    )
    status = models.CharField(
        max_length=16, choices=StatementStatus.choices, default=StatementStatus.DRAFT
    )
    version = models.PositiveIntegerField(default=1)
    # Computed by the database. The supersedes composite foreign key (migration
    # 0003) matches it against the restated row's version, so version n always
    # restates version n - 1 and the chain can neither skip, reorder nor loop.
    previous_version = models.GeneratedField(
        expression=F("version") - 1, output_field=models.IntegerField(), db_persist=True
    )
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )
    restatement_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "statement_type", "period_start", "period_end", "version"],
                name="financial_records_financialstatement_version_unique",
            ),
            models.UniqueConstraint(
                fields=["entity", "statement_type", "period_start", "period_end"],
                condition=Q(status=StatementStatus.VALIDATED),
                name="financial_records_financialstatement_one_validated",
            ),
            models.UniqueConstraint(
                fields=["entity", "statement_type", "period_start", "period_end"],
                condition=Q(status=StatementStatus.DRAFT),
                name="financial_records_financialstatement_one_draft",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="financial_records_financialstatement_version_positive",
            ),
            # (version = 1) = (supersedes IS NULL)
            models.CheckConstraint(
                condition=Q(version=1, supersedes__isnull=True)
                | Q(version__gt=1, supersedes__isnull=False),
                name="financial_records_financialstatement_version_supersedes",
            ),
            # A restatement's reason has at least one non-whitespace character.
            models.CheckConstraint(
                condition=Q(supersedes__isnull=True, restatement_reason="")
                | Q(supersedes__isnull=False, restatement_reason__regex=r"\S"),
                name="financial_records_financialstatement_restatement_reason",
            ),
            models.CheckConstraint(
                condition=Q(period_start__lte=F("period_end")),
                name="financial_records_financialstatement_period_order",
            ),
            models.CheckConstraint(
                condition=Q(currency__regex=_CURRENCY_FORMAT),
                name="financial_records_financialstatement_currency_format",
            ),
            models.CheckConstraint(
                condition=Q(statement_type__in=STATEMENT_TYPES),
                name="financial_records_financialstatement_statement_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(period_type__in=PERIOD_TYPES),
                name="financial_records_financialstatement_period_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(reported_scale__in=SCALES),
                name="financial_records_financialstatement_reported_scale_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=StatementStatus.values),
                name="financial_records_financialstatement_status_valid",
            ),
            # Composite foreign key targets: a restatement restates the previous
            # version of the same statement (same workspace, entity, statement
            # type and period); a fact matches its statement's workspace,
            # entity, period and currency.
            models.UniqueConstraint(
                fields=[
                    "workspace",
                    "entity",
                    "statement_type",
                    "period_start",
                    "period_end",
                    "version",
                    "id",
                ],
                name="financial_records_financialstatement_restatement_key",
            ),
            models.UniqueConstraint(
                fields=[
                    "workspace",
                    "entity",
                    "period_start",
                    "period_end",
                    "period_type",
                    "currency",
                    "id",
                ],
                name="financial_records_financialstatement_fact_key",
            ),
        ]
        indexes = [
            models.Index(
                "workspace", "entity", F("period_end").desc(), name="stmt_ws_entity_end_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.statement_type} {self.period_start}..{self.period_end} v{self.version}"


class StatementLineItem(PublicModel):
    """A raw input row, exactly as entered or uploaded. Never overwritten."""

    # No separate index: the (statement, row_number) key below leads with it.
    statement = models.ForeignKey(
        FinancialStatement, on_delete=models.CASCADE, related_name="line_items", db_index=False
    )
    row_number = models.PositiveIntegerField()
    label = models.CharField(max_length=255)
    # Blank means unmapped.
    line_item_code = models.CharField(max_length=64, choices=_choices(LINE_ITEMS), blank=True)
    # In the statement's reported scale; null when the source cell was blank.
    reported_amount = models.DecimalField(max_digits=30, decimal_places=6, null=True, blank=True)
    raw_value = models.CharField(max_length=64, blank=True)  # e.g. "(1,234.5)"
    source_reference = models.CharField(max_length=64, blank=True)  # e.g. "row 14", "B14"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "row_number"],
                name="financial_records_statementlineitem_row_unique",
            ),
            models.UniqueConstraint(
                fields=["statement", "line_item_code"],
                condition=~Q(line_item_code=""),
                name="financial_records_statementlineitem_code_unique",
            ),
            models.CheckConstraint(
                condition=Q(row_number__gte=1),
                name="financial_records_statementlineitem_row_positive",
            ),
            models.CheckConstraint(
                condition=Q(line_item_code="") | Q(line_item_code__in=LINE_ITEMS),
                name="financial_records_statementlineitem_code_valid",
            ),
            # Composite foreign key target: a fact derives from a mapped row of
            # its own statement, with the same code.
            models.UniqueConstraint(
                fields=["statement", "id", "line_item_code"],
                name="financial_records_statementlineitem_fact_key",
            ),
        ]

    def __str__(self) -> str:
        return f"row {self.row_number}: {self.label}"


class FinancialFact(PublicModel):
    """A verified, normalised figure in base currency units: the engine's only input.

    The period and currency are copied from the statement for indexing; on
    PostgreSQL a composite foreign key keeps them equal to the statement's. A
    missing figure is the absence of a fact, never null or zero.
    """

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="financial_facts"
    )
    # No separate index: the (entity, line_item, period_end) index leads with it.
    entity = models.ForeignKey(
        ReportingEntity, on_delete=models.RESTRICT, related_name="facts", db_index=False
    )
    # No separate index: the (statement, line_item) key below leads with it.
    statement = models.ForeignKey(
        FinancialStatement, on_delete=models.RESTRICT, related_name="facts", db_index=False
    )
    line_item = models.CharField(max_length=64, choices=_choices(LINE_ITEMS))
    period_start = models.DateField()
    period_end = models.DateField()
    period_type = models.CharField(max_length=16, choices=_choices(PERIOD_TYPES))
    currency = models.CharField(max_length=3)
    value = models.DecimalField(max_digits=30, decimal_places=6)
    derived_from = models.OneToOneField(
        StatementLineItem, on_delete=models.RESTRICT, related_name="fact"
    )
    review_status = models.CharField(max_length=16, choices=ReviewStatus.choices)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "line_item"],
                name="financial_records_financialfact_line_item_unique",
            ),
            models.CheckConstraint(
                condition=Q(line_item__in=LINE_ITEMS),
                name="financial_records_financialfact_line_item_valid",
            ),
            models.CheckConstraint(
                condition=Q(review_status__in=ReviewStatus.values),
                name="financial_records_financialfact_review_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["entity", "line_item", "period_end"], name="fact_entity_item_end_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.line_item} {self.period_end}: {self.value} {self.currency}"
