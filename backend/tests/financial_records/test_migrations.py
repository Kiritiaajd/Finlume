"""financial_records migrations on PostgreSQL: composite keys exist, are deferred and reverse."""

from __future__ import annotations

import importlib

import pytest
from django.core.management import call_command
from django.db import connection

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

composite = importlib.import_module("apps.financial_records.migrations.0002_composite_foreign_keys")
NAMES = sorted(name for _, name, *_ in composite.COMPOSITE_KEYS)
SUPERSEDES = "financial_records_financialstatement_supersedes_same_key"


def deferred_foreign_keys() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE contype = 'f' AND condeferrable AND condeferred AND conname = ANY(%s) "
            "ORDER BY conname",
            [NAMES],
        )
        return [name for (name,) in cursor.fetchall()]


def supersedes_definition() -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s", [SUPERSEDES]
        )
        return cursor.fetchone()[0]


def test_every_composite_foreign_key_exists_and_is_deferred():
    assert deferred_foreign_keys() == NAMES


def test_a_restatement_key_matches_the_previous_version():
    definition = supersedes_definition()

    assert "previous_version, supersedes_id)" in definition
    assert "version, id)" in definition


def test_the_restatement_chain_migration_reverses_to_the_previous_key():
    call_command("migrate", "financial_records", "0002", verbosity=0)
    assert deferred_foreign_keys() == NAMES
    assert "previous_version" not in supersedes_definition()

    call_command("migrate", "financial_records", verbosity=0)
    assert "previous_version, supersedes_id)" in supersedes_definition()


def test_the_composite_keys_migrations_reverse_and_reapply():
    call_command("migrate", "financial_records", "0001", verbosity=0)
    assert deferred_foreign_keys() == []

    call_command("migrate", "financial_records", verbosity=0)
    assert deferred_foreign_keys() == NAMES
