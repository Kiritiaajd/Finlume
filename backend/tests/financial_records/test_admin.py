"""Financial records can be inspected, but not added, edited or deleted, from the admin."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def rows(make_statement, make_line_item, make_fact):
    statement = make_statement()
    line_item = make_line_item(statement, "revenue")
    return {
        "documents_sourcedocument": statement.source_document,
        "financial_records_reportingentity": statement.entity,
        "financial_records_financialstatement": statement,
        "financial_records_statementlineitem": line_item,
        "financial_records_financialfact": make_fact(line_item),
    }


@pytest.mark.parametrize(
    "model",
    [
        "documents_sourcedocument",
        "financial_records_reportingentity",
        "financial_records_financialstatement",
        "financial_records_statementlineitem",
        "financial_records_financialfact",
    ],
)
def test_financial_records_admin_is_view_only(admin_client, rows, model):
    obj = rows[model]

    assert admin_client.get(reverse(f"admin:{model}_changelist")).status_code == 200
    assert admin_client.get(reverse(f"admin:{model}_add")).status_code == 403
    assert admin_client.get(reverse(f"admin:{model}_delete", args=[obj.pk])).status_code == 403
    change_page = admin_client.get(reverse(f"admin:{model}_change", args=[obj.pk]))
    assert change_page.status_code == 200
    assert b'name="_save"' not in change_page.content
