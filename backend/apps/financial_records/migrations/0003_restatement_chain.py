"""Version n restates exactly version n - 1; a restatement reason is not only whitespace.

Before this migration, ``supersedes`` only had to point at the same statement
(workspace, entity, type, period), so a version could restate itself or a
later version. Now the database computes ``previous_version = version - 1``,
and the ``supersedes_same_key`` composite foreign key also matches it against
the restated row's ``version``.

The composite key is replaced around the constraint changes, because
PostgreSQL will not drop the unique key it references. Like 0002, the SQL runs
on PostgreSQL only.
"""

import django.db.models.expressions
from django.db import migrations, models

TABLE = "financial_records_financialstatement"
NAME = "financial_records_financialstatement_supersedes_same_key"
KEY = "workspace_id, entity_id, statement_type, period_start, period_end"

PREVIOUS_KEY_SQL = (
    f"ALTER TABLE {TABLE} ADD CONSTRAINT {NAME} FOREIGN KEY ({KEY}, supersedes_id) "
    f"REFERENCES {TABLE} ({KEY}, id) DEFERRABLE INITIALLY DEFERRED"
)
CHAIN_KEY_SQL = (
    f"ALTER TABLE {TABLE} ADD CONSTRAINT {NAME} "
    f"FOREIGN KEY ({KEY}, previous_version, supersedes_id) "
    f"REFERENCES {TABLE} ({KEY}, version, id) DEFERRABLE INITIALLY DEFERRED"
)
DROP_SQL = f"ALTER TABLE {TABLE} DROP CONSTRAINT {NAME}"


def _on_postgresql(sql):
    def run(apps, schema_editor):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(sql)

    return run


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0001_initial"),
        ("financial_records", "0002_composite_foreign_keys"),
        ("workspaces", "0002_backfill_personal_workspaces"),
    ]

    operations = [
        migrations.RunPython(_on_postgresql(DROP_SQL), _on_postgresql(PREVIOUS_KEY_SQL)),
        migrations.RemoveConstraint(
            model_name="financialstatement",
            name="financial_records_financialstatement_restatement_reason",
        ),
        migrations.RemoveConstraint(
            model_name="financialstatement",
            name="financial_records_financialstatement_restatement_key",
        ),
        migrations.AddField(
            model_name="financialstatement",
            name="previous_version",
            field=models.GeneratedField(
                db_persist=True,
                expression=django.db.models.expressions.CombinedExpression(
                    models.F("version"), "-", models.Value(1)
                ),
                output_field=models.IntegerField(),
            ),
        ),
        migrations.AddConstraint(
            model_name="financialstatement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("restatement_reason", ""), ("supersedes__isnull", True)),
                    models.Q(
                        ("restatement_reason__regex", "\\S"),
                        ("supersedes__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="financial_records_financialstatement_restatement_reason",
            ),
        ),
        migrations.AddConstraint(
            model_name="financialstatement",
            constraint=models.UniqueConstraint(
                fields=(
                    "workspace",
                    "entity",
                    "statement_type",
                    "period_start",
                    "period_end",
                    "version",
                    "id",
                ),
                name="financial_records_financialstatement_restatement_key",
            ),
        ),
        migrations.RunPython(_on_postgresql(CHAIN_KEY_SQL), _on_postgresql(DROP_SQL)),
    ]
