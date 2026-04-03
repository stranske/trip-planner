import json
from pathlib import Path

import pytest

from trip_planner.state import (
    AccountPreferenceRecord,
    NotificationPreference,
    TravelerProfile,
    User,
)
from trip_planner.state.repositories import AccountRepository, AccountVersion


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "state" / "accounts"
    return fixtures_dir / name


def _load_fixture(name: str) -> User:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return User.from_dict(payload)


def test_account_loads_leisure_focused_fixture() -> None:
    account = _load_fixture("leisure_user.json")

    payload = account.to_dict()

    assert payload["user_id"] == "user-leisure-1"
    assert payload["account_preferences"]["default_trip_mode"] == "leisure"
    assert payload["traveler_profiles"][0]["leisure_profile_id"] == "leisure-profile-paris"


def test_account_loads_mixed_leisure_business_fixture() -> None:
    account = _load_fixture("mixed_mode_user.json")

    assert len(account.traveler_profiles) == 2
    assert account.traveler_profiles[1].business_profile_id == "business-profile-consulting"
    assert account.account_preferences.default_traveler_profile_id == "traveler-business"


def test_account_loads_multi_profile_fixture() -> None:
    account = _load_fixture("multi_profile_user.json")

    payload = account.to_dict()

    assert len(payload["traveler_profiles"]) == 3
    assert payload["account_preferences"]["preferred_languages"] == ["en-US", "fr-FR"]
    assert payload["traveler_profiles"][2]["profile_kind"] == "family"


def test_traveler_profile_rejects_business_mode_without_business_profile_ref() -> None:
    try:
        TravelerProfile(
            traveler_profile_id="traveler-invalid",
            display_name="Invalid business profile",
            profile_kind="business",
            supported_modes=["business"],
        )
    except ValueError as exc:
        assert "business_profile_id" in str(exc)
    else:
        raise AssertionError("Business traveler profiles should require business_profile_id")


def test_user_rejects_missing_default_traveler_profile_reference() -> None:
    try:
        User(
            user_id="user-1",
            email="user@example.com",
            display_name="Traveler",
            traveler_profiles=[
                TravelerProfile(
                    traveler_profile_id="traveler-1",
                    display_name="Primary leisure",
                    supported_modes=["leisure"],
                    leisure_profile_id="leisure-1",
                )
            ],
            account_preferences=AccountPreferenceRecord(
                default_traveler_profile_id="missing-profile"
            ),
        )
    except ValueError as exc:
        assert "default_traveler_profile_id" in str(exc)
    else:
        raise AssertionError("User should reject unknown default traveler profiles")


def test_account_preferences_reject_scalar_string_list_fields() -> None:
    with pytest.raises(ValueError, match="preferred_languages must be a list"):
        AccountPreferenceRecord.from_dict({"preferred_languages": "en-US"})


def test_traveler_profile_rejects_scalar_string_list_fields() -> None:
    with pytest.raises(ValueError, match="supported_modes must be a list"):
        TravelerProfile.from_dict(
            {
                "traveler_profile_id": "traveler-invalid",
                "display_name": "Invalid traveler",
                "supported_modes": "business",
            }
        )


def test_user_rejects_non_list_traveler_profiles_payload() -> None:
    with pytest.raises(ValueError, match="traveler_profiles must be a list"):
        User.from_dict(
            {
                "user_id": "user-invalid",
                "email": "user@example.com",
                "display_name": "Traveler",
                "traveler_profiles": "traveler-1",
            }
        )


def test_user_rejects_scalar_string_account_tags() -> None:
    with pytest.raises(ValueError, match="account_tags must be a list"):
        User.from_dict(
            {
                "user_id": "user-invalid",
                "email": "user@example.com",
                "display_name": "Traveler",
                "traveler_profiles": [
                    {
                        "traveler_profile_id": "traveler-1",
                        "display_name": "Primary leisure",
                        "supported_modes": ["leisure"],
                        "leisure_profile_id": "leisure-1",
                    }
                ],
                "account_tags": "vip",
            }
        )


def test_account_repository_protocol_can_version_user_state() -> None:
    class InMemoryAccountRepository(AccountRepository):
        def __init__(self) -> None:
            self._users: dict[str, User] = {}
            self._versions: dict[str, list[AccountVersion]] = {}

        def get_user(self, user_id: str) -> User | None:
            return self._users.get(user_id)

        def save_user(self, user: User, *, summary: str = "") -> AccountVersion:
            version = AccountVersion(
                version_id=f"{user.user_id}-v{len(self._versions.get(user.user_id, [])) + 1}",
                user_id=user.user_id,
                recorded_at="2026-04-01T20:00:00Z",
                summary=summary,
            )
            self._users[user.user_id] = user
            self._versions.setdefault(user.user_id, []).append(version)
            return version

        def list_users(self) -> list[User]:
            return list(self._users.values())

        def list_versions(self, user_id: str) -> list[AccountVersion]:
            return list(self._versions.get(user_id, []))

    repo = InMemoryAccountRepository()
    account = _load_fixture("multi_profile_user.json")
    account.account_preferences.notification_preferences.append(
        NotificationPreference(channel="push", cadence="digest", enabled=True)
    )

    first = repo.save_user(account, summary="initial import")
    second = repo.save_user(account, summary="added push digest")

    assert repo.get_user(account.user_id) is account
    assert [version.version_id for version in repo.list_versions(account.user_id)] == [
        first.version_id,
        second.version_id,
    ]
    assert repo.list_users()[0].account_preferences.notification_preferences[-1].channel == "push"
