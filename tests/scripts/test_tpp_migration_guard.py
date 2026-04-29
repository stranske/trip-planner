from scripts import tpp_migration_guard as guard


def test_has_recorded_sub_decision_detects_any_supported_option() -> None:
    assert guard.has_recorded_sub_decision("Decision: B-1")
    assert guard.has_recorded_sub_decision("We selected B-2 after discussion.")
    assert guard.has_recorded_sub_decision("Final: B-3 canonical path")
    assert not guard.has_recorded_sub_decision("No decision recorded yet")


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
