"""A run's entity is in the run's workspace (PostgreSQL composite foreign key).

Same pattern as ``financial_records.0002``: it references the entity's
``(workspace, id)`` key, is ``DEFERRABLE INITIALLY DEFERRED`` like Django's own
foreign keys, and leaves deletion to Django's ``RESTRICT`` handling.
PostgreSQL only.
"""

from django.db import migrations

TABLE = "analysis_analysisrun"
NAME = "analysis_analysisrun_entity_same_workspace"


def add_key(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            f"ALTER TABLE {TABLE} ADD CONSTRAINT {NAME} FOREIGN KEY (workspace_id, entity_id) "
            "REFERENCES financial_records_reportingentity (workspace_id, id) "
            "DEFERRABLE INITIALLY DEFERRED"
        )


def drop_key(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT {NAME}")


class Migration(migrations.Migration):
    dependencies = [
        ("analysis", "0001_initial"),
        ("financial_records", "0003_restatement_chain"),
    ]

    operations = [migrations.RunPython(add_key, drop_key)]
