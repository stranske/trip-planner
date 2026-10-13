"""Private per-account runtime credentials, fail-closed rotation and isolation."""

import json

import pytest

from trip_planner.integrations.tpp.client import TPPConfigurationError
from trip_planner.integrations.tpp.portal_identity import configured_portal_client


def write_store(path, users):
    path.write_text(json.dumps({"schema_version": "tpp-owner-identities/v1", "users": users}))
    path.chmod(0o600)


def test_runtime_identity_rotation_and_no_cross_account_or_shared_fallback(tmp_path, monkeypatch):
    path = tmp_path / "identities.json"
    entry = {
        "namespace": "issuer/audience",
        "subject": "issued-a",
        "authorization": "Bearer individual-a",
    }
    write_store(path, {"local-a": entry})
    monkeypatch.setenv("TRIP_PLANNER_TPP_IDENTITIES_FILE", str(path))
    client = configured_portal_client()
    assert client.resolve_owner("local-a").subject == "issued-a"
    with pytest.raises(TPPConfigurationError):
        client.resolve_owner("local-b")
    write_store(path, {"local-a": {**entry, "authorization": "Bearer rotated-a"}})
    assert client.resolve_owner("local-a").authorization == "Bearer rotated-a"
    monkeypatch.setenv("TPP_ACCESS_TOKEN", "rotated-a")
    with pytest.raises(TPPConfigurationError):
        client.resolve_owner("local-a")
    write_store(path, {})
    with pytest.raises(TPPConfigurationError):
        client.resolve_owner("local-a")


@pytest.mark.parametrize("failure", ["public", "symlink", "malformed", "relative"])
def test_untrusted_store_is_rejected_without_credential_disclosure(tmp_path, monkeypatch, failure):
    path = tmp_path / "identities.json"
    write_store(
        path,
        {"local-a": {"namespace": "google", "subject": "a", "authorization": "Bearer sensitive"}},
    )
    configured_path = path
    if failure == "public":
        path.chmod(0o644)
    elif failure == "symlink":
        configured_path = tmp_path / "link.json"
        configured_path.symlink_to(path)
    elif failure == "malformed":
        path.write_text("invalid sensitive")
    else:
        configured_path = "identities.json"
    monkeypatch.setenv("TRIP_PLANNER_TPP_IDENTITIES_FILE", str(configured_path))
    with pytest.raises(TPPConfigurationError) as caught:
        configured_portal_client().resolve_owner("local-a")
    assert "sensitive" not in str(caught.value)
