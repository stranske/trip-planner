"""Candidate-generation contracts and deterministic first-pass assembly."""

from .generation import generate_candidate_set
from .models import (
    CANDIDATE_FILTER_REASON_CODES,
    SCHEMA_VERSION,
    CandidateExclusion,
    CandidateFilterSummary,
    CandidateSeed,
    CandidateSet,
)

__all__ = [
    "CANDIDATE_FILTER_REASON_CODES",
    "SCHEMA_VERSION",
    "CandidateExclusion",
    "CandidateFilterSummary",
    "CandidateSeed",
    "CandidateSet",
    "generate_candidate_set",
]
