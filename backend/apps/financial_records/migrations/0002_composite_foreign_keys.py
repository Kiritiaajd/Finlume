"""Composite foreign keys that keep related rows consistent across tables.

Django 5.2 has no composite foreign keys, so they are added in SQL. Each one
references a ``*_key`` unique constraint from 0001 and checks what a
single-column key cannot:

- a statement, its entity, its source document and the version it restates
  are in the same workspace (and a restatement has the same entity, statement
  type and period);
- a fact has its statement's workspace, entity, period and currency;
- a fact derives from a mapped row of its own statement, with the same code.

They are ``DEFERRABLE INITIALLY DEFERRED``, like Django's own foreign keys, so a
workspace cascade can delete rows in any order within its transaction. ``ON
DELETE`` stays ``NO ACTION``: Django's ``RESTRICT`` handling decides what may
be deleted. PostgreSQL only; SQLite is never used for real data
(docs/data/DATABASE_CONVENTIONS.md).
"""

from django.db import migrations

STATEMENT = "financial_records_financialstatement"
FACT = "financial_records_financialfact"

# (table, constraint name, columns, referenced table, referenced columns)
COMPOSITE_KEYS = [
    (
        STATEMENT,
        "financial_records_financialstatement_entity_same_workspace",
        "workspace_id, entity_id",
        "financial_records_reportingentity",
        "workspace_id, id",
    ),
    (
        STATEMENT,
        "financial_records_financialstatement_source_same_workspace",
        "workspace_id, source_document_id",
        "documents_sourcedocument",
        "workspace_id, id",
    ),
    (
        STATEMENT,
        "financial_records_financialstatement_supersedes_same_key",
        "workspace_id, entity_id, statement_type, period_start, period_end, supersedes_id",
        STATEMENT,
        "workspace_id, entity_id, statement_type, period_start, period_end, id",
    ),
    (
        FACT,
        "financial_records_financialfact_matches_statement",
        "workspace_id, entity_id, period_start, period_end, period_type, currency, statement_id",
        STATEMENT,
        "workspace_id, entity_id, period_start, period_end, period_type, currency, id",
    ),
    (
        FACT,
        "financial_records_financialfact_derived_from_same_statement",
        "statement_id, derived_from_id, line_item",
        "financial_records_statementlineitem",
        "statement_id, id, line_item_code",
    ),
]


def add_composite_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, name, columns, target, target_columns in COMPOSITE_KEYS:
        # Identifiers are the constants above, never input.
        schema_editor.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({columns}) "
            f"REFERENCES {target} ({target_columns}) DEFERRABLE INITIALLY DEFERRED"
        )


def drop_composite_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, name, *_ in reversed(COMPOSITE_KEYS):
        schema_editor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0001_initial"),
        ("financial_records", "0001_initial"),
    ]

    operations = [migrations.RunPython(add_composite_keys, drop_composite_keys)]
