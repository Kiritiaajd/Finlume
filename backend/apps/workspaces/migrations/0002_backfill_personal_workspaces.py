"""Give every existing user a personal workspace and its owner membership (ADR-0008 §7).

Idempotent: only users without a personal workspace are processed, so running
it again creates nothing. Rows are written in batches with two bulk inserts
per batch.
"""

from itertools import batched

from django.db import migrations

PERSONAL_WORKSPACE_NAME = "Personal"
BATCH_SIZE = 1000


def create_personal_workspaces(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Workspace = apps.get_model("workspaces", "Workspace")
    WorkspaceMembership = apps.get_model("workspaces", "WorkspaceMembership")

    user_ids = list(
        User.objects.filter(personal_workspace__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for batch in batched(user_ids, BATCH_SIZE):
        workspaces = Workspace.objects.bulk_create(
            Workspace(name=PERSONAL_WORKSPACE_NAME, personal_owner_id=pk, created_by_id=pk)
            for pk in batch
        )
        WorkspaceMembership.objects.bulk_create(
            WorkspaceMembership(workspace=ws, user_id=ws.personal_owner_id, role="owner")
            for ws in workspaces
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        # Reversing needs no data step: unapplying 0001 drops both tables.
        migrations.RunPython(create_personal_workspaces, migrations.RunPython.noop),
    ]
