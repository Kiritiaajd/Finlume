"""A report and every run in it share one workspace (PostgreSQL composite foreign keys).

Same pattern as ``financial_records.0002`` and ``analysis.0002``: each key
references a ``(workspace, id)`` unique key, is ``DEFERRABLE INITIALLY
DEFERRED`` like Django's own foreign keys, and leaves deletion to Django.
PostgreSQL only.
"""

from django.db import migrations

TABLE = "reports_reportrun"

# (constraint name, columns, referenced table)
KEYS = [
    ("reports_reportrun_report_same_workspace", "workspace_id, report_id", "reports_report"),
    ("reports_reportrun_run_same_workspace", "workspace_id, run_id", "analysis_analysisrun"),
]


def add_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for name, columns, target in KEYS:
        schema_editor.execute(
            f"ALTER TABLE {TABLE} ADD CONSTRAINT {name} FOREIGN KEY ({columns}) "
            f"REFERENCES {target} (workspace_id, id) DEFERRABLE INITIALLY DEFERRED"
        )


def drop_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for name, _, _ in reversed(KEYS):
        schema_editor.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0001_initial"),
        ("analysis", "0003_report_key"),
    ]

    operations = [migrations.RunPython(add_keys, drop_keys)]
