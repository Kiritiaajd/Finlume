"""CSV statement import (MVP step 4; acceptance criteria 4 and 9, FA-06)."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditEvent
from apps.documents.models import SourceDocument, SourceDocumentKind
from apps.financial_records.models import FinancialStatement
from apps.workspaces.models import WorkspaceRole
from services.errors import ConflictError
from services.statement_analysis import imports

pytestmark = pytest.mark.django_db

FY25 = {
    "statement_type": "income_statement",
    "period_start": "2025-04-01",
    "period_end": "2026-03-31",
    "period_type": "annual",
    "currency": "INR",
    "reported_scale": "crores",
}

GOOD_CSV = (
    b"label,amount,code\n"
    b'Revenue from operations,"1,250.50",revenue\n'
    b"Cost of revenue,(700.25),\n"
    b'Net income,"1,23,456.78",\n'
    b"Exceptional items,,\n"
)


@pytest.fixture(autouse=True)
def private_storage(settings, tmp_path):
    """Each test gets its own private storage folder, so it can see what was written."""
    settings.STORAGES = {
        **settings.STORAGES,
        "private_documents": {
            **settings.STORAGES["private_documents"],
            "OPTIONS": {"location": tmp_path},
        },
    }
    return tmp_path


def stored_files(root):
    return sorted(path for path in root.rglob("*") if path.is_file())


@pytest.fixture
def workspace(make_workspace):
    return make_workspace()


@pytest.fixture
def entity(workspace, make_entity):
    return make_entity(workspace=workspace)


@pytest.fixture
def editor(workspace, add_to_workspace):
    return add_to_workspace(workspace, WorkspaceRole.EDITOR)


@pytest.fixture
def upload(api_client, workspace, entity, editor):
    """POST a CSV import as the editor; returns the response."""

    def post(content=GOOD_CSV, *, name="fy25.csv", headers=None, fields=None, target=None):
        api_client.force_login(editor)
        url = (
            f"/api/v1/workspaces/{workspace.public_id}"
            f"/entities/{(target or entity).public_id}/imports/"
        )
        body = {**FY25, **(fields or {}), "file": SimpleUploadedFile(name, content, "text/csv")}
        return api_client.post(url, body, format="multipart", headers=headers or {})

    return post


def nothing_stored(root):
    return (
        not stored_files(root)
        and not SourceDocument.objects.exists()
        and not FinancialStatement.objects.exists()
    )


# --- A good import ------------------------------------------------------------------------


def test_an_upload_becomes_a_draft_with_proposed_codes(upload, private_storage, editor):
    response = upload()

    body = response.json()
    assert response.status_code == 201, body
    assert (body["status"], body["version"], body["currency"]) == ("draft", 1, "INR")
    assert [
        (
            r["row_number"],
            r["label"],
            r["line_item_code"],
            r["amount"],
            r["raw_value"],
            r["source_reference"],
        )
        for r in body["line_items"]
    ] == [
        (
            1,
            "Revenue from operations",
            "revenue",
            "1250.500000",
            "1,250.50",
            "line 2",
        ),  # code column
        (
            2,
            "Cost of revenue",
            "cost_of_revenue",
            "-700.250000",
            "(700.25)",
            "line 3",
        ),  # name match
        (3, "Net income", "net_income", "123456.780000", "1,23,456.78", "line 4"),
        (4, "Exceptional items", None, None, "", "line 5"),  # unmapped, blank: unknown, not zero
    ]
    assert body["facts"] == []  # nothing is a fact before the user validates the draft
    assert body["warnings"] == []

    document = SourceDocument.objects.get()
    assert body["document"]["id"] == str(document.public_id)
    assert (document.kind, document.original_filename, document.content_type) == (
        SourceDocumentKind.CSV_UPLOAD,
        "fy25.csv",
        "text/csv",
    )
    assert document.size_bytes == len(GOOD_CSV)
    assert document.sha256 == hashlib.sha256(GOOD_CSV).hexdigest() == body["document"]["sha256"]
    assert document.created_by == editor
    assert "fy25" not in document.storage_key  # a random key, never the upload's name
    [stored] = stored_files(private_storage)
    assert stored.read_bytes() == GOOD_CSV
    assert AuditEvent.objects.filter(
        action="document.uploaded", target_public_id=document.public_id
    ).exists()


def test_validating_an_import_gives_traceable_figures_in_base_units(api_client, upload, workspace):
    # Acceptance criteria 4 (normalised figures) and 9 (row, version, document).
    draft = upload().json()

    validated = api_client.post(
        f"/api/v1/workspaces/{workspace.public_id}/statements/{draft['id']}/validate/"
    ).json()

    rows = {row["id"]: row for row in validated["line_items"]}
    assert [
        (f["line_item"], f["value"], rows[f["row_id"]]["source_reference"])
        for f in validated["facts"]
    ] == [
        ("revenue", "12505000000.000000", "line 2"),
        ("cost_of_revenue", "-7002500000.000000", "line 3"),
        ("net_income", "1234567800000.000000", "line 4"),
    ]
    # A cost in parentheses arrives negative; it is flagged, never flipped.
    assert [issue["code"] for issue in validated["issues"]] == ["unexpected_sign"]
    statement = FinancialStatement.objects.get(public_id=draft["id"])
    assert (statement.version, statement.source_document.kind) == (1, SourceDocumentKind.CSV_UPLOAD)


def test_a_file_code_wins_over_a_name_match(upload):
    response = upload(b"label,amount,code\nRevenue,1,\nSales,2,revenue\n")

    rows = response.json()["line_items"]
    assert [(r["label"], r["line_item_code"]) for r in rows] == [
        ("Revenue", None),
        ("Sales", "revenue"),
    ]


def test_a_utf8_byte_order_mark_is_accepted(upload):
    assert upload(b"\xef\xbb\xbflabel,amount\nRevenue,1\n").status_code == 201


def test_a_second_upload_of_the_same_file_is_a_warning(upload):
    first = upload().json()

    response = upload(fields={"period_start": "2024-04-01", "period_end": "2025-03-31"})

    assert response.status_code == 201
    [warning] = response.json()["warnings"]
    assert warning["code"] == "duplicate_file"
    assert warning["document_id"] == first["document"]["id"]


# --- Nothing is stored when something is wrong ------------------------------------------------


def test_a_malformed_row_is_reported_and_nothing_is_stored(upload, private_storage):
    response = upload(b"label,amount\nRevenue,1\nCost,12abc\nTax,1.2345678\n")

    rows = response.json()["error"]["details"]["rows"]
    assert response.status_code == 400
    assert list(rows) == ["3", "4"]  # file line numbers
    assert "Not a number" in rows["3"]["amount"][0]
    assert "6 decimal places" in rows["4"]["amount"][0]
    assert nothing_stored(private_storage)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"label,amount\nRevenue,1\nTotal assets,5,total_assets\n", "Expected 2 columns"),
        (b"label,amount,code\nRevenue,1,\nAssets,5,total_assets\n", "belongs on the balance_sheet"),
        (b"label,amount,code\nRevenue,1,revenue\nSales,5,revenue\n", "already on line 2"),
        (b"label,amount\nRevenue,100000000000000000\n", "Too large once scaled from crores"),
    ],
)
def test_row_rules_match_manual_entry(upload, private_storage, content, message):
    response = upload(content)

    assert response.status_code == 400
    assert message in str(response.json()["error"]["details"]["rows"])
    assert nothing_stored(private_storage)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"label,amount,notes\nRevenue,1,x\n", "Unknown column 'notes'"),
        (b"label,amount\n", "no rows"),
        (b"\xff\xfe\x00l\x00a\x00b\x00e\x00l", "UTF-8"),  # UTF-16
        (b"label,amount\nRevenue,1\x00\n", "not a binary file"),
        (b'label,amount\n"Revenue,1\n', "not valid CSV"),
    ],
)
def test_file_problems_are_reported_and_nothing_is_stored(
    upload, private_storage, content, message
):
    response = upload(content)

    assert response.status_code == 400
    assert message in response.json()["error"]["details"]["file"][0]
    assert nothing_stored(private_storage)


def test_an_empty_file_is_refused(upload, private_storage):
    response = upload(b"")

    assert response.status_code == 400
    assert "file" in response.json()["error"]["details"]
    assert nothing_stored(private_storage)


def test_the_row_cap_applies(upload, settings, private_storage):
    settings.MAX_IMPORT_ROWS = 2

    response = upload(b"label,amount\nA,1\nB,2\nC,3\n")

    assert response.status_code == 400
    assert "more than 2 rows" in response.json()["error"]["details"]["file"][0]
    assert nothing_stored(private_storage)


@pytest.mark.parametrize("size", [101, 200 * 1024], ids=["just over", "far over"])
def test_an_oversized_file_is_refused_before_anything_is_stored(
    upload, settings, private_storage, size
):
    # "far over" is refused from Content-Length alone, before the body is read.
    settings.MAX_UPLOAD_BYTES = 100
    content = b"label,amount\n" + b"Revenue,1\n" * (size // 10)

    response = upload(content[: max(size, 101)])

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert nothing_stored(private_storage)


def test_a_far_oversized_request_is_refused_without_reading_its_body(upload, settings, monkeypatch):
    from rest_framework.parsers import MultiPartParser

    def must_not_parse(*args, **kwargs):
        raise AssertionError("the body was parsed")

    monkeypatch.setattr(MultiPartParser, "parse", must_not_parse)
    settings.MAX_UPLOAD_BYTES = 100

    assert upload(b"label,amount\n" + b"Revenue,1\n" * 20_000).status_code == 413


def test_an_existing_statement_for_the_period_is_a_conflict(
    upload, entity, make_statement, private_storage
):
    from datetime import date

    existing = make_statement(
        entity=entity, period_start=date(2025, 4, 1), period_end=date(2026, 3, 31)
    )

    response = upload()

    assert response.status_code == 409
    assert stored_files(private_storage) == []
    assert list(SourceDocument.objects.all()) == [existing.source_document]


def test_a_failure_after_storing_the_file_removes_it(upload, private_storage, monkeypatch):
    def fail(**kwargs):
        raise ConflictError("Created concurrently.")

    monkeypatch.setattr(imports, "create_statement", fail)

    response = upload()

    assert response.status_code == 409
    assert nothing_stored(private_storage)


# --- Idempotency -----------------------------------------------------------------------------


def test_replaying_an_idempotency_key_returns_the_original_import(upload, private_storage):
    key = str(uuid.uuid4())

    first = upload(headers={"Idempotency-Key": key})
    again = upload(headers={"Idempotency-Key": key})

    assert (first.status_code, again.status_code) == (201, 201)
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["document"] == first.json()["document"]
    assert SourceDocument.objects.count() == 1
    assert len(stored_files(private_storage)) == 1


def test_an_idempotency_key_reused_for_another_file_is_a_conflict(upload):
    key = str(uuid.uuid4())
    upload(headers={"Idempotency-Key": key})

    response = upload(b"label,amount\nRevenue,2\n", headers={"Idempotency-Key": key})

    assert response.status_code == 409
    assert SourceDocument.objects.count() == 1


def test_an_idempotency_key_must_be_a_uuid(upload, private_storage):
    response = upload(headers={"Idempotency-Key": "not-a-uuid"})

    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["error"]["details"]
    assert nothing_stored(private_storage)


# --- Access ------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [None, WorkspaceRole.VIEWER])
def test_viewers_and_outsiders_cannot_upload(
    api_client, workspace, entity, add_to_workspace, make_user, private_storage, role
):
    api_client.force_login(make_user() if role is None else add_to_workspace(workspace, role))

    response = api_client.post(
        f"/api/v1/workspaces/{workspace.public_id}/entities/{entity.public_id}/imports/",
        {**FY25, "file": SimpleUploadedFile("fy25.csv", GOOD_CSV, "text/csv")},
        format="multipart",
    )

    assert response.status_code == (404 if role is None else 403)
    assert nothing_stored(private_storage)


def test_another_workspaces_entity_is_not_found(upload, make_entity, private_storage):
    response = upload(target=make_entity())

    assert response.status_code == 404
    assert not SourceDocument.objects.filter(kind=SourceDocumentKind.CSV_UPLOAD).exists()
    assert stored_files(private_storage) == []


def test_anonymous_callers_get_401(api_client, workspace, entity):
    response = api_client.post(
        f"/api/v1/workspaces/{workspace.public_id}/entities/{entity.public_id}/imports/",
        {**FY25, "file": SimpleUploadedFile("fy25.csv", GOOD_CSV, "text/csv")},
        format="multipart",
    )

    assert response.status_code == 401


def test_only_multipart_uploads_are_accepted(api_client, workspace, entity, editor):
    api_client.force_login(editor)

    response = api_client.post(
        f"/api/v1/workspaces/{workspace.public_id}/entities/{entity.public_id}/imports/",
        FY25,
        format="json",
    )

    assert response.status_code == 415
