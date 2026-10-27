"""Request and response shapes for entities, statements and the line-item taxonomy.

Input rules (MVP plan step 3, FOUNDATION_AUDIT FA-15), all answered with a
field-level ``400 validation_error``:

- amounts are decimal **strings**; JSON numbers are refused, so no value ever
  passes through a binary float;
- at most 6 decimal places, and a magnitude below 10^24 both as entered and
  once scaled to base units, so every figure fits ``numeric(30,6)``;
- a line-item code only on its own statement type, and at most once per
  statement;
- the currency is three uppercase letters, and the period does not end
  before it starts.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from rest_framework import serializers

from apps.documents.models import SourceDocument
from apps.financial_records.models import (
    LINE_ITEMS,
    PERIOD_TYPES,
    SCALES,
    STATEMENT_TYPES,
    EntityType,
    FinancialFact,
    FinancialStatement,
    ReportingEntity,
    StatementLineItem,
)
from domain.financial_statements import LineItem, Scale
from domain.financial_statements.line_items import NON_NEGATIVE_ITEMS, NON_POSITIVE_ITEMS
from domain.validation import Issue
from services.statement_analysis.rows import RowInput, amount_problem, row_problems

MAX_ROWS = 500

_CURRENCY = r"^[A-Z]{3}$"


class AmountField(serializers.Field[Decimal, str, str, Any]):
    """A figure sent as a decimal string, e.g. ``"1250.50"`` or ``"-3.25"``."""

    default_error_messages = {  # noqa: RUF012 - DRF's documented pattern
        "not_a_string": 'Send amounts as decimal strings, for example "1250.50".',
        "invalid": "A valid number is required.",
        "too_long": "Amounts have at most 64 characters.",
    }

    def to_internal_value(self, data: Any) -> Decimal:
        if not isinstance(data, str):
            self.fail("not_a_string")
        if len(data) > 64:
            self.fail("too_long")
        try:
            value = Decimal(data.strip())
        except InvalidOperation:
            self.fail("invalid")
        if not value.is_finite():
            self.fail("invalid")
        problem = amount_problem(value)
        if problem:
            raise serializers.ValidationError(problem)
        return value

    def to_representation(self, value: Decimal) -> str:
        return format(value, "f")


class LineItemInputSerializer(serializers.Serializer[Any]):
    # DRF's metaclass moves declared fields off the class, so naming one ``label``
    # (the model column) is safe; only the stubs see a clash with ``Field.label``.
    label = serializers.CharField(max_length=255)  # type: ignore[assignment]
    line_item_code = serializers.ChoiceField(choices=LINE_ITEMS, allow_blank=True, default="")
    amount = AmountField(allow_null=True, default=None)
    source_reference = serializers.CharField(max_length=64, allow_blank=True, default="")

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        values: dict[str, Any] = super().to_internal_value(data)
        # In a partial update (PATCH) DRF skips required checks and defaults on
        # nested fields too, but a row always replaces a whole row.
        if "label" not in values:
            raise serializers.ValidationError(
                {"label": [self.fields["label"].error_messages["required"]]}
            )
        values.setdefault("line_item_code", "")
        values.setdefault("amount", None)
        values.setdefault("source_reference", "")
        # Keep the text exactly as entered, for audit (DATA_MODEL §4.7).
        raw = data.get("amount") if isinstance(data, Mapping) else None
        values["raw_value"] = raw if isinstance(raw, str) else ""
        return values


class _StatementHeaderSerializer(serializers.Serializer[Any]):
    """The fields that describe a statement, whatever its rows come from."""

    statement_type = serializers.ChoiceField(choices=STATEMENT_TYPES)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    period_type = serializers.ChoiceField(choices=PERIOD_TYPES)
    currency = serializers.RegexField(_CURRENCY, max_length=3)
    reported_scale = serializers.ChoiceField(choices=SCALES)


class StatementImportSerializer(_StatementHeaderSerializer):
    """A statement CSV (multipart) and the statement it holds."""

    file = serializers.FileField(max_length=255)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["period_start"] > attrs["period_end"]:
            raise serializers.ValidationError({"period_end": ["The period ends before it starts."]})
        return attrs


class StatementInputSerializer(_StatementHeaderSerializer):
    """Create a draft, or (``partial=True`` with ``context["statement"]``) edit one."""

    line_items = serializers.ListField(
        child=LineItemInputSerializer(), max_length=MAX_ROWS, required=False
    )

    default_error_messages = {  # noqa: RUF012
        "resend_rows": "Send line_items again when changing statement_type or reported_scale.",
    }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        existing: FinancialStatement | None = self.context.get("statement")

        def final(field: str) -> Any:
            """The value after this request: sent, or kept from the draft being edited."""
            return attrs[field] if field in attrs else getattr(existing, field)

        if final("period_start") > final("period_end"):
            raise serializers.ValidationError({"period_end": ["The period ends before it starts."]})

        rows = attrs.get("line_items")
        if rows is None:
            if existing is None:
                attrs["line_items"] = rows = []
            elif any(
                field in attrs and attrs[field] != getattr(existing, field)
                for field in ("statement_type", "reported_scale")
            ):
                raise serializers.ValidationError(
                    {"line_items": [self.error_messages["resend_rows"]]}
                )
            else:
                return attrs
        statement_type: str = final("statement_type")
        scale = Scale[str(final("reported_scale")).upper()]
        errors = _row_errors(rows, statement_type, scale)
        if errors:
            raise serializers.ValidationError({"line_items": errors})
        return attrs


def _row_errors(
    rows: list[RowInput], statement_type: str, scale: Scale
) -> dict[str, dict[str, list[str]]]:
    """The shared row rules, keyed by row index like DRF's own list errors."""
    problems = row_problems(rows, statement_type=statement_type, scale=scale)
    return {str(index): fields for index, fields in problems.items()}


class RestatementInputSerializer(serializers.Serializer[Any]):
    """Restate ``context["statement"]``; without ``line_items`` its rows are copied."""

    reason = serializers.CharField(max_length=2000)  # trimmed; blank is refused
    line_items = serializers.ListField(
        child=LineItemInputSerializer(), max_length=MAX_ROWS, required=False
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        statement: FinancialStatement = self.context["statement"]
        rows = attrs.get("line_items")
        if rows is not None:
            scale = Scale[statement.reported_scale.upper()]
            errors = _row_errors(rows, statement.statement_type, scale)
            if errors:
                raise serializers.ValidationError({"line_items": errors})
        return attrs


class EntityInputSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)
    entity_type = serializers.ChoiceField(choices=EntityType.choices)
    default_currency = serializers.RegexField(
        _CURRENCY, max_length=3, required=False, allow_blank=True, default=""
    )
    fiscal_year_end_month = serializers.IntegerField(
        min_value=1, max_value=12, required=False, allow_null=True, default=None
    )


# --- Responses -------------------------------------------------------------------------


def entity_data(entity: ReportingEntity) -> dict[str, Any]:
    return {
        "id": entity.public_id,
        "name": entity.name,
        "entity_type": entity.entity_type,
        "default_currency": entity.default_currency or None,
        "fiscal_year_end_month": entity.fiscal_year_end_month,
        "created_at": entity.created_at,
    }


def statement_data(statement: FinancialStatement) -> dict[str, Any]:
    """Expects ``entity`` and ``supersedes`` already loaded."""
    return {
        "id": statement.public_id,
        "entity_id": statement.entity.public_id,
        "statement_type": statement.statement_type,
        "period_start": statement.period_start,
        "period_end": statement.period_end,
        "period_type": statement.period_type,
        "currency": statement.currency,
        "reported_scale": statement.reported_scale,
        "status": statement.status,
        "version": statement.version,
        "supersedes_id": statement.supersedes.public_id if statement.supersedes else None,
        "restatement_reason": statement.restatement_reason or None,
        "created_at": statement.created_at,
        "updated_at": statement.updated_at,
    }


def line_item_data(row: StatementLineItem) -> dict[str, Any]:
    return {
        "id": row.public_id,
        "row_number": row.row_number,
        "label": row.label,
        "line_item_code": row.line_item_code or None,
        "amount": None if row.reported_amount is None else format(row.reported_amount, "f"),
        "raw_value": row.raw_value,
        "source_reference": row.source_reference or None,
    }


def document_data(document: SourceDocument) -> dict[str, Any]:
    """A source document's metadata. The file itself has no URL (ADR-0005)."""
    return {
        "id": document.public_id,
        "kind": document.kind,
        "filename": document.original_filename or None,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256 or None,
        "created_at": document.created_at,
    }


def fact_data(fact: FinancialFact) -> dict[str, Any]:
    """A normalised figure in base units. Expects ``derived_from`` already loaded."""
    return {
        "line_item": fact.line_item,
        "value": format(fact.value, "f"),
        "row_id": fact.derived_from.public_id,
        "review_status": fact.review_status,
    }


def issue_data(issue: Issue) -> dict[str, Any]:
    return {
        "code": issue.code.value,
        "severity": issue.severity.value,
        "message": issue.message,
        "line_items": [item.value for item in issue.line_items],
    }


def taxonomy_data(item: LineItem) -> dict[str, Any]:
    if item in NON_NEGATIVE_ITEMS:
        sign = "non_negative"
    elif item in NON_POSITIVE_ITEMS:
        sign = "non_positive"
    else:
        sign = "signed"
    return {
        "code": item.value,
        "statement_type": item.statement_type.value,
        "label": item.value.replace("_", " ").capitalize(),
        "definition": item.definition,
        "sign": sign,
    }
