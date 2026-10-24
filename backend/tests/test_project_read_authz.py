"""GET /projects/{id} must authenticate and check membership on every read, never from a cache."""

from helpers import setup_project


def test_non_member_gets_404_even_after_owner_read_the_project(client_factory):
    alice, bob, eve = client_factory("alice"), client_factory("bob"), client_factory("eve")
    ids = setup_project(alice, bob)
    url = f"/api/v1/projects/{ids['project']}"

    owner_read = alice.get(url)
    assert owner_read.status_code == 200, owner_read.text
    assert owner_read.json()["id"] == ids["project"]

    denied = eve.get(url)
    assert denied.status_code == 404, denied.text
    assert "name" not in denied.text
    assert ids["project"] not in denied.text


def test_unauthenticated_get_is_401_even_when_project_was_read_before(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    url = f"/api/v1/projects/{ids['project']}"

    assert alice.get(url).status_code == 200
    anonymous = client_factory().get(url)
    assert anonymous.status_code == 401, anonymous.text
    assert ids["project"] not in anonymous.text


def test_owner_sees_updated_record_on_next_get(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    url = f"/api/v1/projects/{ids['project']}"

    assert alice.get(url).json()["name"] == "payments-lite"
    updated = alice.patch(url, json={"name": "payments-renamed"})
    assert updated.status_code == 200, updated.text

    fresh = alice.get(url)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["name"] == "payments-renamed"
