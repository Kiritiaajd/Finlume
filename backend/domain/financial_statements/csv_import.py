"""The statement CSV format: pure parsing rules, no I/O (MVP step 4).

A file holds one statement. The first non-empty line is the header, with the
columns ``label`` and ``amount`` and, optionally, ``code``, in any order and
any case. Every other non-empty line is one row:

- ``label``: the line as it appears in the source; required.
- ``amount``: blank for an empty cell, otherwise a number in the statement's
  reported scale. Accepted: ``1234.56``, ``-1234.56``, ``(1,234.56)`` for a
  negative, and comma thousands separators in any grouping, such as the Indian
  ``1,23,456.78``. The decimal separator is a point. The value is read
  exactly; it never passes through a binary float.
- ``code``: optional; a canonical line-item code, in any case.

Problems with the file as a whole raise ``CsvFormatError``. Problems with a
row are collected per line and column, so a user can fix them all at once.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from .line_items import LineItem, StatementType

COLUMNS = ("label", "amount", "code")
REQUIRED_COLUMNS = ("label", "amount")
MAX_LABEL_LENGTH = 255
MAX_AMOUNT_LENGTH = 64

# Digits with optional comma grouping (commas only between digits), then an
# optional decimal point and fraction.
_NUMBER = re.compile(r"\d+(?:,\d+)*(?:\.\d+)?")


class CsvFormatError(ValueError):
    """The file cannot be read as a statement CSV at all."""


@dataclass(frozen=True)
class CsvRow:
    line: int  # the row's line number in the file, header included
    label: str
    code: str  # "" when the file gives none
    amount: Decimal | None  # None for an empty cell
    raw_amount: str  # the cell exactly as written


@dataclass(frozen=True)
class ParsedCsv:
    rows: tuple[CsvRow, ...]
    #: Row problems: line number → column → messages.
    errors: Mapping[int, Mapping[str, tuple[str, ...]]] = field(default_factory=dict)


def parse_amount(text: str) -> Decimal | None:
    """An amount cell to an exact ``Decimal``; ``None`` for an empty cell.

    Raises ``ValueError`` with a user-facing message for anything else.
    """
    cell = text.strip()
    if not cell:
        return None
    negative = False
    if cell.startswith("(") and cell.endswith(")"):
        negative, cell = True, cell[1:-1].strip()
    elif cell.startswith("-"):
        negative, cell = True, cell[1:]
    if not _NUMBER.fullmatch(cell):
        raise ValueError(
            "Not a number. Write amounts like 1234.56, -1234.56, (1,234.56) or 1,23,456.78."
        )
    value = Decimal(cell.replace(",", ""))
    return -value if negative else value


def parse_statement_csv(text: str, *, max_rows: int) -> ParsedCsv:
    """Read every row of a statement CSV, collecting row problems by line."""
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    columns: dict[str, int] | None = None
    rows: list[CsvRow] = []
    errors: dict[int, dict[str, tuple[str, ...]]] = {}
    try:
        for cells in reader:
            if not any(cell.strip() for cell in cells):
                continue  # blank lines carry nothing
            if columns is None:
                columns = _header(cells)
                continue
            if len(rows) + len(errors) >= max_rows:
                raise CsvFormatError(f"The file has more than {max_rows} rows.")
            row = _row(reader.line_num, cells, columns)
            if isinstance(row, CsvRow):
                rows.append(row)
            else:
                errors[reader.line_num] = row
    except csv.Error:
        raise CsvFormatError(
            f"Line {reader.line_num} is not valid CSV. Check its quotation marks."
        ) from None
    if columns is None:
        raise CsvFormatError("The file is empty.")
    if not rows and not errors:
        raise CsvFormatError("The file has a header but no rows.")
    return ParsedCsv(rows=tuple(rows), errors=errors)


def propose_line_item(label: str, statement_type: StatementType) -> LineItem | None:
    """The code whose name matches ``label`` exactly, ignoring case, spaces and underscores.

    Only codes of ``statement_type`` are proposed. There is no fuzzy matching:
    an unmatched label stays unmapped until the user maps it.
    """
    wanted = _normalise(label)
    for item in LineItem:
        if item.statement_type is statement_type and _normalise(item.value) == wanted:
            return item
    return None


def _normalise(text: str) -> str:
    return " ".join(text.replace("_", " ").lower().split())


def _header(cells: list[str]) -> dict[str, int]:
    names = [cell.strip().lower() for cell in cells]
    unknown = [name for name in names if name not in COLUMNS]
    if unknown:
        raise CsvFormatError(
            f"Unknown column {unknown[0]!r}. The columns are label, amount and, optionally, code."
        )
    duplicated = {name for name in names if names.count(name) > 1}
    if duplicated:
        raise CsvFormatError(f"The column {sorted(duplicated)[0]!r} appears more than once.")
    missing = [name for name in REQUIRED_COLUMNS if name not in names]
    if missing:
        raise CsvFormatError(f"The header has no {missing[0]!r} column.")
    return {name: index for index, name in enumerate(names)}


def _row(
    line: int, cells: list[str], columns: dict[str, int]
) -> CsvRow | dict[str, tuple[str, ...]]:
    """The parsed row, or its problems by column."""
    if len(cells) != len(columns):
        return {"row": (f"Expected {len(columns)} columns, found {len(cells)}.",)}

    problems: dict[str, tuple[str, ...]] = {}
    label = cells[columns["label"]].strip()
    if not label:
        problems["label"] = ("A label is required.",)
    elif len(label) > MAX_LABEL_LENGTH:
        problems["label"] = (f"Labels have at most {MAX_LABEL_LENGTH} characters.",)

    raw_amount = cells[columns["amount"]]
    amount: Decimal | None = None
    if len(raw_amount) > MAX_AMOUNT_LENGTH:
        problems["amount"] = (f"Amounts have at most {MAX_AMOUNT_LENGTH} characters.",)
    else:
        try:
            amount = parse_amount(raw_amount)
        except ValueError as exc:
            problems["amount"] = (str(exc),)

    code = cells[columns["code"]].strip().lower() if "code" in columns else ""
    if code and code not in {item.value for item in LineItem}:
        problems["code"] = (f"Unknown line-item code {code!r}.",)

    if problems:
        return problems
    return CsvRow(line=line, label=label, code=code, amount=amount, raw_amount=raw_amount)
