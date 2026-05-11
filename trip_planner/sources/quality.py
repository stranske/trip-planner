"""Deterministic source-quality scoring and explanation engine.

Implements the behavioral model from ``docs/source-quality-model.md``: freshness,
channel fit, provenance strength, conflict state, and traveler relevance are scored
independently and fused into a bounded confidence summary that ranking explanations
and planner tools can consume.

The scorer accepts :class:`SourceRecord` and :class:`ProvenanceReference` inputs in
the same call to support fused summaries across multiple contributions for one
subject.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from statistics import fmean, median
from typing import Any

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_probability,
    require_strings,
)

from . import schema
from .models import QualityValueFitSummary, SourceRecord, SourceTrustSignals
from .provenance import ProvenanceReference

CONFIDENCE_LABELS: tuple[str, ...] = (
    "very_high",
    "high",
    "moderate",
    "uncertain",
    "sparse",
)


SourceLike = SourceRecord | ProvenanceReference


_CATEGORY_OPERATIONAL_PRIOR: dict[str, float] = {
    "official_operational": 0.90,
    "managed_travel_policy": 0.85,
    "commercial_inventory": 0.75,
    "editorial": 0.65,
    "specialist_non_commercial": 0.55,
    "ratings_reviews": 0.55,
}


_CATEGORY_TRAVELER_RELEVANCE_PRIOR: dict[str, float] = {
    "editorial": 0.80,
    "specialist_non_commercial": 0.75,
    "ratings_reviews": 0.70,
    "commercial_inventory": 0.65,
    "official_operational": 0.60,
    "managed_travel_policy": 0.55,
}


_CATEGORY_TAGS: dict[str, str] = {
    "official_operational": "official",
    "managed_travel_policy": "managed-channel",
    "commercial_inventory": "commercial",
    "ratings_reviews": "crowd-review",
    "editorial": "editorial",
    "specialist_non_commercial": "specialist",
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _round(value: float) -> float:
    return round(value, 4)


def _confidence_label(score: float) -> str:
    if score >= 0.80:
        return "very_high"
    if score >= 0.65:
        return "high"
    if score >= 0.45:
        return "moderate"
    if score >= 0.25:
        return "uncertain"
    return "sparse"


@dataclass(slots=True)
class SourceQualityScore:
    """Typed score for a single source contribution.

    All numeric fields are in ``[0.0, 1.0]``. ``confidence_label`` is one of
    :data:`CONFIDENCE_LABELS`.
    """

    source_id: str
    source_category: str
    confidence: float
    confidence_label: str
    freshness_score: float
    channel_fit_score: float
    provenance_strength: float
    traveler_relevance: float
    explanation_fragment: str
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.source_id, "source_id")
        if self.source_category not in schema.SOURCE_CATEGORIES:
            raise ValueError(f"source_category must be one of {schema.SOURCE_CATEGORIES}")
        if self.confidence_label not in CONFIDENCE_LABELS:
            raise ValueError(f"confidence_label must be one of {CONFIDENCE_LABELS}")
        for field_name in (
            "confidence",
            "freshness_score",
            "channel_fit_score",
            "provenance_strength",
            "traveler_relevance",
        ):
            require_probability(getattr(self, field_name), field_name)
        require_non_empty(self.explanation_fragment, "explanation_fragment")
        require_strings(self.tags, "tags")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceConfidenceSummary:
    """Bounded fused summary over one or more source contributions.

    ``conflict_detected`` is ``True`` when the contributing sources disagree
    materially on quality/value/fit signals; ``conflict_summary`` describes the
    disagreement in traveler-facing language. ``mutates_state`` is always
    ``False`` so this shape is safe for read-only planner tools.
    """

    subject_kind: str
    confidence: float
    confidence_label: str
    contributing_source_count: int
    category_counts: dict[str, int]
    freshness_summary: str
    conflict_detected: bool
    conflict_summary: str
    explanation_fragments: list[str]
    tags: list[str]
    per_source_scores: list[SourceQualityScore] = field(default_factory=list)
    mutates_state: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.subject_kind not in schema.PROVENANCE_SUBJECT_KINDS:
            raise ValueError(f"subject_kind must be one of {schema.PROVENANCE_SUBJECT_KINDS}")
        require_probability(self.confidence, "confidence")
        if self.confidence_label not in CONFIDENCE_LABELS:
            raise ValueError(f"confidence_label must be one of {CONFIDENCE_LABELS}")
        require_non_negative(self.contributing_source_count, "contributing_source_count")
        for key, value in self.category_counts.items():
            if not isinstance(key, str) or not key:
                raise ValueError("category_counts keys must be non-empty strings")
            if key not in schema.SOURCE_CATEGORIES:
                raise ValueError(f"category_counts keys must be from {schema.SOURCE_CATEGORIES}")
            require_non_negative(value, f"category_counts[{key}]")
        require_strings(self.explanation_fragments, "explanation_fragments")
        require_strings(self.tags, "tags")
        require_strings(self.notes, "notes")
        if self.mutates_state:
            raise ValueError("SourceConfidenceSummary is read-only; mutates_state must be False")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceQualityScorer:
    """Deterministic source-quality scoring engine.

    All scoring is pure-function on the input contracts so identical inputs
    always produce identical outputs regardless of iteration order. The engine
    keeps stale, conflicting, or sparse sources visible rather than deleting
    them; their confidence_label and tags surface the uncertainty.
    """

    FRESHNESS_HALF_LIFE_DAYS: float = 45.0
    CONFLICT_SIGNAL_GAP: float = 0.35

    def score_source(
        self,
        record: SourceRecord,
        *,
        traveler_relevance_hint: float | None = None,
        intended_option_kind: str | None = None,
    ) -> SourceQualityScore:
        if not isinstance(record, SourceRecord):
            raise ValueError("record must be a SourceRecord")
        return self._score(
            source_id=record.source_id,
            source_category=record.category,
            supported_option_kinds=tuple(record.supported_option_kinds),
            trust_signals=record.trust_signals,
            quality_summary=record.quality_summary,
            traveler_relevance_hint=traveler_relevance_hint,
            intended_option_kind=intended_option_kind,
            display_label=record.display_name or record.provider_name,
        )

    def score_provenance(
        self,
        reference: ProvenanceReference,
        *,
        traveler_relevance_hint: float | None = None,
        intended_option_kind: str | None = None,
    ) -> SourceQualityScore:
        if not isinstance(reference, ProvenanceReference):
            raise ValueError("reference must be a ProvenanceReference")
        trust = reference.trust_snapshot or SourceTrustSignals(
            freshness_days=reference.freshness_days_at_capture
        )
        quality = reference.quality_value_fit or QualityValueFitSummary()
        return self._score(
            source_id=reference.source_id,
            source_category=reference.source_category,
            supported_option_kinds=(),
            trust_signals=trust,
            quality_summary=quality,
            traveler_relevance_hint=traveler_relevance_hint,
            intended_option_kind=intended_option_kind,
            display_label=reference.source_id,
        )

    def summarize(
        self,
        records: Iterable[SourceLike],
        *,
        subject_kind: str = "option",
        traveler_relevance_hint: float | None = None,
        intended_option_kind: str | None = None,
    ) -> SourceConfidenceSummary:
        if subject_kind not in schema.PROVENANCE_SUBJECT_KINDS:
            raise ValueError(f"subject_kind must be one of {schema.PROVENANCE_SUBJECT_KINDS}")
        record_list = list(records)
        for entry in record_list:
            if not isinstance(entry, (SourceRecord, ProvenanceReference)):
                raise ValueError(
                    "summarize() inputs must be SourceRecord or ProvenanceReference instances"
                )

        if not record_list:
            return SourceConfidenceSummary(
                subject_kind=subject_kind,
                confidence=0.0,
                confidence_label="sparse",
                contributing_source_count=0,
                category_counts={},
                freshness_summary="no source records",
                conflict_detected=False,
                conflict_summary="",
                explanation_fragments=[
                    "No supporting sources were attached, so this option carries uncertainty.",
                ],
                tags=["sparse"],
                per_source_scores=[],
                notes=["empty input"],
            )

        per_source: list[SourceQualityScore] = []
        for entry in record_list:
            if isinstance(entry, SourceRecord):
                per_source.append(
                    self.score_source(
                        entry,
                        traveler_relevance_hint=traveler_relevance_hint,
                        intended_option_kind=intended_option_kind,
                    )
                )
            else:
                per_source.append(
                    self.score_provenance(
                        entry,
                        traveler_relevance_hint=traveler_relevance_hint,
                        intended_option_kind=intended_option_kind,
                    )
                )

        per_source.sort(key=lambda item: (-item.confidence, item.source_category, item.source_id))

        category_counts: dict[str, int] = {}
        for score in per_source:
            category_counts[score.source_category] = (
                category_counts.get(score.source_category, 0) + 1
            )

        freshness_days = self._collect_freshness_days(record_list)
        freshness_summary = self._summarize_freshness(freshness_days)

        conflict_detected, conflict_summary = self._detect_conflicts(record_list)

        base_confidence = fmean(score.confidence for score in per_source)
        coverage_bonus = min(0.08, 0.025 * max(0, len(per_source) - 1))
        diversity_bonus = min(0.06, 0.02 * (len(category_counts) - 1))
        conflict_penalty = 0.18 if conflict_detected else 0.0
        sparse_penalty = 0.10 if len(per_source) == 1 else 0.0

        confidence = _round(
            _clamp(
                base_confidence
                + coverage_bonus
                + diversity_bonus
                - conflict_penalty
                - sparse_penalty
            )
        )
        label = _confidence_label(confidence)

        tags = self._summary_tags(per_source, conflict_detected, len(per_source))
        fragments = self._summary_fragments(
            label=label,
            conflict_detected=conflict_detected,
            conflict_summary=conflict_summary,
        )

        return SourceConfidenceSummary(
            subject_kind=subject_kind,
            confidence=confidence,
            confidence_label=label,
            contributing_source_count=len(per_source),
            category_counts=category_counts,
            freshness_summary=freshness_summary,
            conflict_detected=conflict_detected,
            conflict_summary=conflict_summary,
            explanation_fragments=fragments,
            tags=tags,
            per_source_scores=per_source,
        )

    def _score(
        self,
        *,
        source_id: str,
        source_category: str,
        supported_option_kinds: tuple[str, ...],
        trust_signals: SourceTrustSignals,
        quality_summary: QualityValueFitSummary,
        traveler_relevance_hint: float | None,
        intended_option_kind: str | None,
        display_label: str,
    ) -> SourceQualityScore:
        if traveler_relevance_hint is not None:
            require_probability(traveler_relevance_hint, "traveler_relevance_hint")
        if (
            intended_option_kind is not None
            and intended_option_kind not in schema.SOURCE_OPTION_KINDS
        ):
            raise ValueError(f"intended_option_kind must be one of {schema.SOURCE_OPTION_KINDS!r}")

        freshness_score = self._freshness_score(trust_signals)
        channel_fit_score = self._channel_fit_score(
            source_category, supported_option_kinds, intended_option_kind
        )
        provenance_strength = self._provenance_strength(source_category, trust_signals)
        traveler_relevance = self._traveler_relevance(
            source_category, traveler_relevance_hint, quality_summary
        )

        weighted = (
            freshness_score * 0.25
            + channel_fit_score * 0.20
            + provenance_strength * 0.30
            + traveler_relevance * 0.25
        )
        # quality_summary.confidence (when present) is a small final adjustment toward the
        # source's own self-reported certainty, but never overrides the structural signals.
        if quality_summary.confidence is not None:
            weighted = 0.85 * weighted + 0.15 * quality_summary.confidence

        confidence = _round(_clamp(weighted))
        label = _confidence_label(confidence)
        tags = self._per_source_tags(
            source_category=source_category,
            freshness_score=freshness_score,
            confidence_label=label,
            channel_fit_score=channel_fit_score,
            provenance_strength=provenance_strength,
        )
        fragment = self._per_source_fragment(
            display_label=display_label,
            source_category=source_category,
            label=label,
            freshness_score=freshness_score,
        )

        return SourceQualityScore(
            source_id=source_id,
            source_category=source_category,
            confidence=confidence,
            confidence_label=label,
            freshness_score=_round(freshness_score),
            channel_fit_score=_round(channel_fit_score),
            provenance_strength=_round(provenance_strength),
            traveler_relevance=_round(traveler_relevance),
            explanation_fragment=fragment,
            tags=tags,
        )

    def _freshness_score(self, trust: SourceTrustSignals) -> float:
        days = trust.freshness_days
        if days is None:
            base = 0.40
        else:
            # exponential-style decay anchored at FRESHNESS_HALF_LIFE_DAYS so a
            # one-week-old source still scores high while a 6-month-old source
            # falls below 0.25.
            base = self.FRESHNESS_HALF_LIFE_DAYS / (self.FRESHNESS_HALF_LIFE_DAYS + max(0, days))
        confidence_modifier = trust.freshness_confidence
        if confidence_modifier is None:
            return _clamp(base)
        return _clamp(0.7 * base + 0.3 * confidence_modifier)

    def _channel_fit_score(
        self,
        category: str,
        supported_kinds: tuple[str, ...],
        intended_option_kind: str | None,
    ) -> float:
        category_prior = _CATEGORY_OPERATIONAL_PRIOR.get(category, 0.55)
        if intended_option_kind is None:
            return category_prior
        if not supported_kinds:
            # unknown coverage — keep the category prior but apply a small penalty
            return _clamp(category_prior - 0.10)
        if intended_option_kind in supported_kinds:
            return _clamp(category_prior + 0.10)
        return _clamp(category_prior - 0.20)

    def _provenance_strength(self, category: str, trust: SourceTrustSignals) -> float:
        components: list[float] = []
        if trust.operational_reliability is not None:
            components.append(trust.operational_reliability)
        if trust.review_consistency is not None:
            components.append(trust.review_consistency)
        if trust.editorial_independence is not None:
            # editorial independence reduces commercial-bias risk and is blended
            # with the other reliability signals.
            components.append(trust.editorial_independence)
        if trust.commerciality is not None:
            # commerciality is informative but does not penalize: commercial-inventory
            # sources are expected to be commercial. We scale it lightly toward 0.5.
            components.append(0.4 + 0.2 * trust.commerciality)
        if not components:
            return _CATEGORY_OPERATIONAL_PRIOR.get(category, 0.55) * 0.7
        return _clamp(fmean(components))

    def _traveler_relevance(
        self,
        category: str,
        hint: float | None,
        quality_summary: QualityValueFitSummary,
    ) -> float:
        prior = _CATEGORY_TRAVELER_RELEVANCE_PRIOR.get(category, 0.55)
        fit_signal = quality_summary.fit_signal
        if hint is not None and fit_signal is not None:
            blended = 0.4 * prior + 0.3 * hint + 0.3 * fit_signal
        elif hint is not None:
            blended = 0.5 * prior + 0.5 * hint
        elif fit_signal is not None:
            blended = 0.5 * prior + 0.5 * fit_signal
        else:
            blended = prior
        return _clamp(blended)

    def _per_source_tags(
        self,
        *,
        source_category: str,
        freshness_score: float,
        confidence_label: str,
        channel_fit_score: float,
        provenance_strength: float,
    ) -> list[str]:
        tags: list[str] = []
        category_tag = _CATEGORY_TAGS.get(source_category)
        if category_tag:
            tags.append(category_tag)
        if freshness_score < 0.35:
            tags.append("stale")
        elif freshness_score >= 0.85:
            tags.append("fresh")
        if provenance_strength < 0.40:
            tags.append("weak-provenance")
        if channel_fit_score < 0.40:
            tags.append("off-channel")
        if confidence_label == "sparse":
            tags.append("sparse")
        return list(dict.fromkeys(tags))

    def _per_source_fragment(
        self,
        *,
        display_label: str,
        source_category: str,
        label: str,
        freshness_score: float,
    ) -> str:
        readable_category = source_category.replace("_", " ")
        if label == "very_high":
            tone = "Strong"
        elif label == "high":
            tone = "Solid"
        elif label == "moderate":
            tone = "Mixed"
        elif label == "uncertain":
            tone = "Uncertain"
        else:
            tone = "Sparse"
        freshness_note = ""
        if freshness_score < 0.35:
            freshness_note = " (stale)"
        elif freshness_score >= 0.85:
            freshness_note = " (recent)"
        return f"{tone} {readable_category} signal from {display_label}{freshness_note}."

    def _summary_tags(
        self,
        per_source: Sequence[SourceQualityScore],
        conflict_detected: bool,
        count: int,
    ) -> list[str]:
        tags: list[str] = []
        for score in per_source:
            for tag in score.tags:
                if tag not in tags:
                    tags.append(tag)
        if conflict_detected and "conflict" not in tags:
            tags.append("conflict")
        if count == 1 and "sparse" not in tags:
            tags.append("sparse")
        return tags

    def _summary_fragments(
        self,
        *,
        label: str,
        conflict_detected: bool,
        conflict_summary: str,
    ) -> list[str]:
        fragments: list[str] = []
        if label == "very_high":
            fragments.append(
                "Multiple consistent sources support this option, so confidence is very high."
            )
        elif label == "high":
            fragments.append("Source coverage is solid and the available signals agree.")
        elif label == "moderate":
            fragments.append(
                "Source coverage is mixed; weigh the available signals against your own priorities."
            )
        elif label == "uncertain":
            fragments.append(
                "Source coverage is thin or aging, so this option carries notable uncertainty."
            )
        else:
            fragments.append(
                "Source coverage is sparse; the option remains visible but with low confidence."
            )
        if conflict_detected and conflict_summary:
            fragments.append(conflict_summary)
        elif conflict_detected:
            fragments.append(
                "Sources disagree materially on this option; review tradeoffs carefully."
            )
        return fragments

    def _detect_conflicts(self, records: Sequence[SourceLike]) -> tuple[bool, str]:
        per_axis: dict[str, list[float]] = {"quality": [], "value": [], "fit": []}
        for entry in records:
            if isinstance(entry, SourceRecord):
                quality_summary = entry.quality_summary
            else:
                quality_summary = entry.quality_value_fit or QualityValueFitSummary()
            if quality_summary.quality_signal is not None:
                per_axis["quality"].append(quality_summary.quality_signal)
            if quality_summary.value_signal is not None:
                per_axis["value"].append(quality_summary.value_signal)
            if quality_summary.fit_signal is not None:
                per_axis["fit"].append(quality_summary.fit_signal)

        disagreements: list[str] = []
        for axis_name in ("quality", "value", "fit"):
            values = per_axis[axis_name]
            if len(values) < 2:
                continue
            gap = max(values) - min(values)
            if gap >= self.CONFLICT_SIGNAL_GAP:
                disagreements.append(
                    f"{axis_name} signal spans {min(values):.2f}–{max(values):.2f} across sources"
                )

        if not disagreements:
            return False, ""
        return True, "Sources disagree: " + "; ".join(disagreements) + "."

    def _collect_freshness_days(self, records: Sequence[SourceLike]) -> list[int]:
        days: list[int] = []
        for entry in records:
            if isinstance(entry, SourceRecord):
                value = entry.trust_signals.freshness_days
            else:
                value = entry.freshness_days_at_capture
                if value is None and entry.trust_snapshot is not None:
                    value = entry.trust_snapshot.freshness_days
            if value is not None:
                days.append(value)
        return days

    def _summarize_freshness(self, days: list[int]) -> str:
        if not days:
            return "freshness unknown"
        if len(days) == 1:
            return f"freshness {days[0]} days"
        return f"freshness span {min(days)}–{max(days)} days (median {int(median(days))})"


def summarize_sources(
    records: Iterable[SourceLike],
    *,
    subject_kind: str = "option",
    traveler_relevance_hint: float | None = None,
    intended_option_kind: str | None = None,
) -> SourceConfidenceSummary:
    """Module-level convenience wrapper around :class:`SourceQualityScorer`.

    Planner tools and ranking explanation builders should call this helper rather
    than instantiating the scorer themselves so future tuning of the scoring
    weights stays in one place.
    """

    return SourceQualityScorer().summarize(
        records,
        subject_kind=subject_kind,
        traveler_relevance_hint=traveler_relevance_hint,
        intended_option_kind=intended_option_kind,
    )
