import subprocess

from scripts import tpp_migration_guard as guard


def test_has_recorded_sub_decision_detects_any_supported_option() -> None:
    assert guard.has_recorded_sub_decision("Decision: B-1")
    assert guard.has_recorded_sub_decision("We selected B-2 after discussion.")
    assert guard.has_recorded_sub_decision("Final: B-3 canonical path")
    assert not guard.has_recorded_sub_decision("No decision recorded yet")
    assert not guard.has_recorded_sub_decision("Sub-decision (B-1 / B-2 / B-3) is pending.")
    assert not guard.has_recorded_sub_decision("Choose B-1 or B-2 or B-3 in the PR body.")
    assert not guard.has_recorded_sub_decision("B-1 and B-2 are both under consideration.")


def test_has_recorded_sub_decision_accepts_single_explicit_choice_line() -> None:
    pr_body = "\n".join(
        [
            "Sub-decision options considered: B-1 / B-2 / B-3.",
            "Chosen sub-decision: B-2.",
        ]
    )
    assert guard.has_recorded_sub_decision(pr_body)


def test_has_recorded_sub_decision_accepts_single_checked_checkbox() -> None:
    pr_body = "\n".join(
        [
            "- [ ] B-1 canonical services subtree",
            "- [x] B-2 shared integrations subtree",
            "- [ ] B-3 alternate location",
        ]
    )

    assert guard.has_recorded_sub_decision(pr_body)


def test_has_recorded_sub_decision_rejects_multiple_checked_checkboxes() -> None:
    pr_body = "\n".join(
        [
            "- [x] B-1 canonical services subtree",
            "- [x] B-2 shared integrations subtree",
            "- [ ] B-3 alternate location",
        ]
    )

    assert not guard.has_recorded_sub_decision(pr_body)


def test_parse_rename_records_filters_non_rename_rows() -> None:
    diff_output = "\n".join(
        [
            "R100\ttrip_planner/app/services/tpp_polling_service.py\ttrip_planner/integrations/tpp/services/polling.py",
            "M\ttrip_planner/app/services/planner.py",
            "R094\ta.py\tb.py",
        ]
    )

    records = guard.parse_rename_records(diff_output)

    assert records == [
        (
            "trip_planner/app/services/tpp_polling_service.py",
            "trip_planner/integrations/tpp/services/polling.py",
        ),
        ("a.py", "b.py"),
    ]


def test_find_blocked_tpp_moves_only_includes_guarded_tpp_paths() -> None:
    records = [
        (
            "trip_planner/app/services/tpp_result_service.py",
            "trip_planner/integrations/tpp/services/results.py",
        ),
        (
            "trip_planner/app/services/planner.py",
            "trip_planner/integrations/tpp/services/planner.py",
        ),
        ("trip_planner/app/models/tpp.py", "trip_planner/integrations/tpp/models.py"),
    ]

    blocked = guard.find_blocked_tpp_moves(records)

    assert blocked == [
        (
            "trip_planner/app/services/tpp_result_service.py",
            "trip_planner/integrations/tpp/services/results.py",
        ),
        ("trip_planner/app/models/tpp.py", "trip_planner/integrations/tpp/models.py"),
    ]


def test_resolve_diff_ranges_fetches_missing_github_base_ref(monkeypatch) -> None:
    existing_refs: set[str] = set()
    fetched_refs: list[str] = []

    def fake_git_ref_exists(ref_name: str) -> bool:
        return ref_name in existing_refs

    def fake_fetch_remote_ref(ref_name: str) -> None:
        fetched_refs.append(ref_name)
        existing_refs.add(f"refs/remotes/origin/{ref_name}")

    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setattr(guard, "_git_ref_exists", fake_git_ref_exists)
    monkeypatch.setattr(guard, "_fetch_remote_ref", fake_fetch_remote_ref)
    monkeypatch.setattr(guard, "_git_rev_exists", lambda _rev_name: False)

    assert guard._resolve_diff_ranges() == ["origin/main...HEAD", "origin/main..HEAD"]
    assert fetched_refs == ["main"]


def test_collect_rename_diff_output_falls_back_to_two_dot_diff(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_git(args: list[str]) -> str:
        diff_range = args[-1]
        calls.append(diff_range)
        if diff_range == "origin/main...HEAD":
            raise subprocess.CalledProcessError(returncode=128, cmd=args)
        return (
            "R100\ttrip_planner/app/services/tpp_result_service.py\t"
            "trip_planner/integrations/tpp/services/results.py\n"
        )

    monkeypatch.setattr(
        guard,
        "_resolve_diff_ranges",
        lambda: ["origin/main...HEAD", "origin/main..HEAD"],
    )
    monkeypatch.setattr(guard, "_run_git", fake_run_git)

    assert guard._collect_rename_diff_output().startswith("R100\t")
    assert calls == ["origin/main...HEAD", "origin/main..HEAD"]
