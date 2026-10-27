"""Operator-only ownership recovery (ADR-0008 §3).

    python manage.py recover_workspace_owner <workspace_id> <email> --reason "..."

Makes one active member of the workspace's organization an owner, and only
when every current owner's account is inactive. The change is audited as
``workspace.ownership_recovered``; the command prints the event ID. There is
deliberately no API for this.
"""

from __future__ import annotations

import getpass
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError, CommandParser

from services.errors import ConflictError
from services.workspaces import recover_workspace_owner


def _operator() -> str:
    try:
        return getpass.getuser()
    except OSError:  # no login name in some containers
        return "unknown"


class Command(BaseCommand):
    help = "Make an organization member owner of a workspace whose owners are all inactive."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("workspace_id", type=UUID)
        parser.add_argument("email", help="Email of the new owner")
        parser.add_argument("--reason", required=True, help="Recorded in the audit trail")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            event = recover_workspace_owner(
                workspace_id=options["workspace_id"],
                new_owner_email=options["email"],
                reason=options["reason"],
                operator=_operator(),
            )
        except ConflictError as exc:
            raise CommandError(exc.message) from None
        self.stdout.write(
            self.style.SUCCESS(f"Ownership recovered. Audit event {event.public_id}.")
        )
