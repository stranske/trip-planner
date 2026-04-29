"""Guards against accidental dimension-name drift in schema constants.

These tests enforce that TRADEOFF_DIMENSION_KEYS, POLARITY_MAP, and
DIMENSION_DESCRIPTIONS remain fully synchronized so that any rename,
addition, or deletion fails loudly rather than silently.
"""

from __future__ import annotations

import re

import pytest

from trip_planner.preferences.schema import (
    DIMENSION_DESCRIPTIONS,
    POLARITY_MAP,
    TRADEOFF_DIMENSION_KEYS,
)

# Frozen reference set — update this list if/when a new dimension is formally added.
_EXPECTED_DIMENSION_KEYS: frozenset[str] = frozenset(
    {
        "movement_vs_friction",
        "recovery_vs_intensity",
        "nature_vs_culture",
        "structure_vs_elasticity",
        "breadth_vs_depth",
        "self_reliance_vs_convenience",
        "historic_vs_contemporary",
        "scenic_transit_vs_destination_time",
        "route_coherence_vs_eclectic_contrast",
        "social_energy_vs_solitude",
        "iconic_vs_discovery",
    }
)


def test_dimension_keys_match_expected_set() -> None:
    """TRADEOFF_DIMENSION_KEYS must match the frozen canonical set exactly."""
    assert set(TRADEOFF_DIMENSION_KEYS) == _EXPECTED_DIMENSION_KEYS, (
        f"extra: {set(TRADEOFF_DIMENSION_KEYS) - _EXPECTED_DIMENSION_KEYS}, "
        f"missing: {_EXPECTED_DIMENSION_KEYS - set(TRADEOFF_DIMENSION_KEYS)}"
    )


def test_polarity_map_covers_all_dimension_keys() -> None:
    """Every key in TRADEOFF_DIMENSION_KEYS must appear in POLARITY_MAP."""
    missing = set(TRADEOFF_DIMENSION_KEYS) - set(POLARITY_MAP)
    extra = set(POLARITY_MAP) - set(TRADEOFF_DIMENSION_KEYS)
    assert not missing, f"POLARITY_MAP missing keys: {missing}"
    assert not extra, f"POLARITY_MAP has unexpected keys: {extra}"


def test_dimension_descriptions_covers_all_dimension_keys() -> None:
    """Every key in TRADEOFF_DIMENSION_KEYS must appear in DIMENSION_DESCRIPTIONS."""
    missing = set(TRADEOFF_DIMENSION_KEYS) - set(DIMENSION_DESCRIPTIONS)
    extra = set(DIMENSION_DESCRIPTIONS) - set(TRADEOFF_DIMENSION_KEYS)
    assert not missing, f"DIMENSION_DESCRIPTIONS missing keys: {missing}"
    assert not extra, f"DIMENSION_DESCRIPTIONS has unexpected keys: {extra}"


def test_polarity_map_entries_are_two_element_tuples() -> None:
    """Each POLARITY_MAP entry must be a (negative_pole, positive_pole) pair of non-empty strings."""
    for key, poles in POLARITY_MAP.items():
        assert len(poles) == 2, f"POLARITY_MAP[{key!r}] must have exactly 2 poles, got {len(poles)}"
        assert poles[0] and poles[1], f"POLARITY_MAP[{key!r}] poles must be non-empty strings"


def test_dimension_descriptions_entries_are_three_element_tuples() -> None:
    """Each DIMENSION_DESCRIPTIONS entry must be (description, negative_note, positive_note)."""
    for key, desc in DIMENSION_DESCRIPTIONS.items():
        assert (
            len(desc) == 3
        ), f"DIMENSION_DESCRIPTIONS[{key!r}] must have 3 elements, got {len(desc)}"
        assert all(
            s for s in desc
        ), f"DIMENSION_DESCRIPTIONS[{key!r}] must contain non-empty strings"


@pytest.mark.parametrize("key", TRADEOFF_DIMENSION_KEYS)
def test_dimension_key_naming_convention(key: str) -> None:
    """Dimension keys must use snake_case and contain exactly one 'vs' separator."""
    assert re.fullmatch(r"[a-z][a-z_]*[a-z]", key), f"Key {key!r} must be lowercase snake_case"
    vs_count = key.count("_vs_")
    assert vs_count == 1, f"Key {key!r} must contain exactly one '_vs_' separator, found {vs_count}"


def test_dimension_keys_are_unique() -> None:
    """TRADEOFF_DIMENSION_KEYS must not contain duplicates."""
    assert len(TRADEOFF_DIMENSION_KEYS) == len(set(TRADEOFF_DIMENSION_KEYS))


def test_dimension_keys_count() -> None:
    """Explicitly verify there are 11 canonical dimensions."""
    assert (
        len(TRADEOFF_DIMENSION_KEYS) == 11
    ), f"Expected 11 canonical dimensions, found {len(TRADEOFF_DIMENSION_KEYS)}"
