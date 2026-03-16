from trip_planner.preferences.autonomy import (
    AutonomyFeedback,
    PlanningAutonomyProfile,
)


def test_autonomy_feedback_supports_more_system_initiative() -> None:
    profile = PlanningAutonomyProfile()
    updated = profile.apply_feedback(
        AutonomyFeedback(
            feedback_kind="do_more_before_asking",
            trip_stage="initial_design",
            strength=0.8,
            note="Do more before asking me again.",
        )
    )

    before = profile.behavior_for_stage("initial_design")
    after = updated.behavior_for_stage("initial_design")

    assert after.target_research_passes > before.target_research_passes
    assert (
        updated.preference_for_stage("initial_design").checkpoint_frequency
        < profile.preference_for_stage("initial_design").checkpoint_frequency
    )


def test_autonomy_feedback_supports_showing_options_sooner() -> None:
    profile = PlanningAutonomyProfile()
    updated = profile.apply_feedback(
        AutonomyFeedback(
            feedback_kind="show_options_sooner",
            trip_stage="inventory_selection",
            strength=0.9,
            note="Show me options sooner.",
        )
    )

    behavior = updated.behavior_for_stage("inventory_selection")

    assert behavior.surface_options_early is True
    assert behavior.target_options_before_checkpoint < 4


def test_autonomy_profile_can_vary_by_stage() -> None:
    profile = PlanningAutonomyProfile()
    updated = profile.apply_feedback(
        AutonomyFeedback(
            feedback_kind="do_more_before_asking",
            trip_stage="initial_design",
            strength=0.7,
        )
    )
    updated = updated.apply_feedback(
        AutonomyFeedback(
            feedback_kind="ask_me_earlier",
            trip_stage="in_trip_adjustment",
            strength=0.7,
        )
    )

    assert (
        updated.preference_for_stage("initial_design").checkpoint_frequency
        < updated.preference_for_stage("in_trip_adjustment").checkpoint_frequency
    )
