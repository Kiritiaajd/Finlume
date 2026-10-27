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

from apps.financial_records.models import (
    LINE_ITEMS,
    PERIOD_TYPES,
    SCALES,
    STATEMENT_TYPES,
    EntityType,
    FinancialStatement,
    ReportingEntity,
    StatementLineItem,
)
from domain.financial_statements import LineItem, Scale
from domain.financial_statements.line_items import NON_NEGATIVE_ITEMS, NON_POSITIVE_ITEMS

MAX_ABS = Decimal("1E+24")  # numeric(30,6)
MAX_DECIMAL_PLACES = 6
MAX_ROWS = 500

_CURRENCY = r"^[A-Z]{3}$"


class AmountField(serializers.Field[Decimal, str, str, Any]):
    """A figure sent as a decimal string, e.g. ``"1250.50"`` or ``"-3.25"``."""

    default_error_messages = {  # noqa: RUF012 - DRF's documented pattern
        "not_a_string": 'Send amounts as decimal strings, for example "1250.50".',
        "invalid": "A valid number is required.",
        "too_long": "Amounts have at most 64 characters.",
        "decimal_places": f"Amounts have at most {MAX_DECIMAL_PLACES} decimal places.",
        "too_large": "Amounts must be smaller than 10^24.",
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
        exponent = value.normalize().as_tuple().exponent
        if isinstance(exponent, int) and -exponent > MAX_DECIMAL_PLACES:
            self.fail("decimal_places")
        if abs(value) >= MAX_ABS:
            self.fail("too_large")
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


class StatementInputSerializer(serializers.Serializer[Any]):
    """Create a draft, or (``partial=True`` with ``context["statement"]``) edit one."""

    statement_type = serializers.ChoiceField(choices=STATEMENT_TYPES)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    period_type = serializers.ChoiceField(choices=PERIOD_TYPES)
    currency = serializers.RegexField(_CURRENCY, max_length=3)
    reported_scale = serializers.ChoiceField(choices=SCALES)
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
    rows: list[dict[str, Any]], statement_type: str, scale: Scale
) -> dict[str, dict[str, list[str]]]:
    """Rules that need the whole statement: code placement, duplicates, scaled size.

    Keyed by row index, like DRF's own list errors.
    """
    errors: dict[str, dict[str, list[str]]] = {}
    seen: dict[str, int] = {}
    for index, row in enumerate(rows):
        key = str(index)
        code, amount = row["line_item_code"], row["amount"]
        if code:
            home = LineItem(code).statement_type.value
            if home != statement_type:
                errors.setdefault(key, {})["line_item_code"] = [
                    f"{code} belongs on the {home}, not the {statement_type}."
                ]
            elif code in seen:
                errors.setdefault(key, {})["line_item_code"] = [
                    f"{code} is already on row {seen[code] + 1}."
                ]
            else:
                seen[code] = index
        if amount is not None and abs(amount.scaleb(scale.value)) >= MAX_ABS:
            errors.setdefault(key, {})["amount"] = [
                f"Too large once scaled from {scale.name.lower()} to units."
            ]
    return errors


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
