"""Pagination and ordering rules of list endpoints (API conventions, "Pagination")."""

from __future__ import annotations

import pytest

from apps.financial_records.models import EntityType, ReportingEntity

from .contract import assert_matches_contract

pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace(make_workspace):
    return make_workspace()


@pytest.fixture
def client(api_client, workspace):
    api_client.force_login(workspace.memberships.get().user)
    return api_client


def entities_url(workspace, query=""):
    return f"/api/v1/workspaces/{workspace.public_id}/entities/{query}"


def make_entities(workspace, count):
    ReportingEntity.objects.bulk_create(
        ReportingEntity(
            workspace=workspace, name=f"Entity {n:03d}", entity_type=EntityType.BUSINESS
        )
        for n in range(count)
    )


def test_pages_hold_fifty_by_default_and_link_to_the_next(client, workspace):
    make_entities(workspace, 51)

    first = client.get(entities_url(workspace))
    second = client.get(first.json()["next"])

    assert_matches_contract(first, "get", entities_url(workspace))
    assert (first.json()["count"], len(first.json()["results"])) == (51, 50)
    assert first.json()["previous"] is None
    assert (len(second.json()["results"]), second.json()["next"]) == (1, None)
    assert second.json()["previous"] is not None


@pytest.mark.parametrize(("requested", "served"), [("10", 10), ("200", 200), ("1000", 200)])
def test_the_page_size_can_be_chosen_up_to_two_hundred(client, workspace, requested, served):
    make_entities(workspace, 201)

    response = client.get(entities_url(workspace, f"?page_size={requested}"))

    assert len(response.json()["results"]) == served


def test_a_page_beyond_the_end_is_not_found_in_the_envelope(client, workspace):
    make_entities(workspace, 3)

    response = client.get(entities_url(workspace, "?page=9"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_walking_every_page_never_repeats_or_skips_an_item(client, workspace):
    make_entities(workspace, 25)

    seen = []
    url = entities_url(workspace, "?page_size=7")
    while url:
        body = client.get(url).json()
        seen += [item["id"] for item in body["results"]]
        url = body["next"]

    assert len(seen) == len(set(seen)) == 25


def test_entities_are_listed_by_name(client, workspace):
    for name in ("Zeta Co", "alpha Co", "Beta Co"):
        ReportingEntity.objects.create(
            workspace=workspace, name=name, entity_type=EntityType.BUSINESS
        )

    names = [item["name"] for item in client.get(entities_url(workspace)).json()["results"]]

    assert names == sorted(names)
