"""Import one statement from a CSV file as a draft to review (MVP step 4, FR-013, FR-014).

The upload becomes a draft statement whose rows carry a proposed code each:
the code column when the file has one, otherwise an exact name match (no
fuzzy guessing). The user reviews and corrects the rows like any draft, and
validating it creates the facts (step 3). Nothing becomes a fact without that
review.

All or nothing: a file or row problem is reported in full and nothing is
stored, neither the file nor any row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.documents.models import SourceDocument, SourceDocumentKind
from apps.financial_records.models import FinancialStatement, ReportingEntity
from apps.workspaces.models import Workspace
from domain.financial_statements import Scale, StatementType
from domain.financial_statements.csv_import import (
    CsvFormatError,
    ParsedCsv,
    parse_statement_csv,
    propose_line_item,
)
from services.documents import CSV_CONTENT_TYPE, decode_csv, delete_file, fingerprint, store_file
from services.errors import ConflictError, InvalidInput

from .rows import RowInput, row_problems
from .statements import create_statement, ensure_new_statement


@dataclass(frozen=True)
class ImportOutcome:
    statement: FinancialStatement
    document: SourceDocument
    #: An earlier upload of the same file to this workspace, if any (a warning).
    duplicate_of: SourceDocument | None


@transaction.atomic
def import_statement_csv(
    *,
    actor: User,
    workspace: Workspace,
    entity: ReportingEntity,
    data: bytes,
    filename: str,
    idempotency_key: UUID | None,
    max_rows: int,
    statement_type: str,
    period_start: date,
    period_end: date,
    period_type: str,
    currency: str,
    reported_scale: str,
) -> ImportOutcome:
    """A draft statement from ``data``, with the file kept privately as its source.

    Repeating a request with the same ``idempotency_key`` returns the original
    import; the same key with another file, or for another entity, is a 409.
    """
    sha256 = fingerprint(data)
    if idempotency_key is not None:
        earlier = SourceDocument.objects.filter(
            workspace=workspace, created_by=actor, idempotency_key=idempotency_key
        ).first()
        if earlier is not None:
            return _replay(earlier, sha256=sha256, entity=entity)

    rows = _rows_or_problems(
        decode_csv(data),
        max_rows=max_rows,
        statement_type=statement_type,
        scale=Scale[reported_scale.upper()],
    )
    ensure_new_statement(
        entity=entity,
        statement_type=statement_type,
        period_start=period_start,
        period_end=period_end,
    )

    stored = store_file(workspace=workspace, data=data)
    try:
        try:
            with transaction.atomic():
                document = SourceDocument.objects.create(
                    workspace=workspace,
                    kind=SourceDocumentKind.CSV_UPLOAD,
                    created_by=actor,
                    original_filename=filename[:255],
                    content_type=CSV_CONTENT_TYPE,
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                    storage_key=stored.storage_key,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:  # the same key, sent twice at the same moment
            raise ConflictError(
                "An upload with this Idempotency-Key is already in progress."
            ) from None
        statement = create_statement(
            actor=actor,
            workspace=workspace,
            entity=entity,
            statement_type=statement_type,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            currency=currency,
            reported_scale=reported_scale,
            rows=rows,
            source=document,
        )
    except BaseException:
        # The transaction rolls back the rows; the file is not transactional.
        delete_file(stored.storage_key)
        raise

    duplicate_of = _earlier_upload(document)
    AuditEvent.record(
        "document.uploaded",
        actor=actor,
        workspace=workspace,
        target=document,
        kind=document.kind,
        size_bytes=document.size_bytes,
        duplicate=duplicate_of is not None,
    )
    return ImportOutcome(statement=statement, document=document, duplicate_of=duplicate_of)


def _rows_or_problems(
    text: str, *, max_rows: int, statement_type: str, scale: Scale
) -> list[RowInput]:
    """The rows to store, with proposed codes; every problem at once otherwise."""
    try:
        parsed = parse_statement_csv(text, max_rows=max_rows)
    except CsvFormatError as exc:
        raise InvalidInput({"file": [str(exc)]}) from None

    rows = _with_proposed_codes(parsed, StatementType(statement_type))
    problems: dict[int, dict[str, list[str]]] = {
        line: {column: list(messages) for column, messages in fields.items()}
        for line, fields in parsed.errors.items()
    }
    lines = [row.line for row in parsed.rows]
    for index, fields in row_problems(
        rows, statement_type=statement_type, scale=scale, names=[f"line {n}" for n in lines]
    ).items():
        for field, messages in fields.items():
            column = "code" if field == "line_item_code" else field
            problems.setdefault(lines[index], {})[column] = messages
    if problems:
        raise InvalidInput({"rows": {str(line): problems[line] for line in sorted(problems)}})
    return rows


def _with_proposed_codes(parsed: ParsedCsv, statement_type: StatementType) -> list[RowInput]:
    """Codes from the file first; then an exact name match, unless already taken."""
    taken = {row.code for row in parsed.rows if row.code}
    rows: list[RowInput] = []
    for row in parsed.rows:
        code = row.code
        if not code:
            proposed = propose_line_item(row.label, statement_type)
            if proposed is not None and proposed.value not in taken:
                code = proposed.value
                taken.add(code)
        rows.append(
            {
                "label": row.label,
                "line_item_code": code,
                "amount": row.amount,
                "raw_value": row.raw_amount,
                "source_reference": f"line {row.line}",
            }
        )
    return rows


def _replay(document: SourceDocument, *, sha256: str, entity: ReportingEntity) -> ImportOutcome:
    statement = document.statements.order_by("pk").first()
    if statement is None or document.sha256 != sha256 or statement.entity_id != entity.pk:
        raise ConflictError("This Idempotency-Key was already used for a different upload.")
    return ImportOutcome(
        statement=statement, document=document, duplicate_of=_earlier_upload(document)
    )


def _earlier_upload(document: SourceDocument) -> SourceDocument | None:
    return (
        SourceDocument.objects.filter(
            workspace_id=document.workspace_id, sha256=document.sha256, pk__lt=document.pk
        )
        .order_by("pk")
        .first()
    )
