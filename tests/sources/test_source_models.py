from trip_planner.sources import QualityValueFitSummary, SourceRecord, SourceTrustSignals


def test_source_record_supports_editorial_leisure_source() -> None:
    record = SourceRecord(
        source_id="michelin-green-guide",
        provider_name="Michelin",
        display_name="Michelin Green Guide",
        category="editorial",
        coverage_scope="regional",
        supported_option_kinds=["route", "activity"],
        coverage_regions=["France"],
        base_url="https://guide.michelin.com/",
        default_locale="en-US",
        trust_signals=SourceTrustSignals(
            freshness_days=30,
            freshness_confidence=0.6,
            commerciality=0.2,
            editorial_independence=0.8,
            operational_reliability=0.5,
            review_consistency=0.4,
            notes=["Useful for route-based discovery rather than live inventory."],
        ),
        quality_summary=QualityValueFitSummary(
            quality_signal=0.8,
            value_signal=0.6,
            fit_signal=0.7,
            confidence=0.7,
            notes=["Strong curation for travelers who like independent wandering."],
        ),
        notes=["Leisure discovery source."],
    )

    payload = record.to_dict()

    assert payload["category"] == "editorial"
    assert payload["quality_summary"]["fit_signal"] == 0.7
    assert payload["trust_signals"]["editorial_independence"] == 0.8


def test_source_record_supports_managed_travel_source() -> None:
    record = SourceRecord(
        source_id="navan-travel",
        provider_name="Navan",
        display_name="Navan Travel",
        category="managed_travel_policy",
        coverage_scope="global",
        supported_option_kinds=["flight", "lodging", "car", "policy"],
        base_url="https://navan.com/",
        trust_signals=SourceTrustSignals(
            freshness_days=2,
            freshness_confidence=0.9,
            commerciality=0.8,
            editorial_independence=0.2,
            operational_reliability=0.8,
            review_consistency=0.6,
        ),
        business_approval_status="preferred",
        business_approval_notes=["Default managed-travel channel for enterprise clients."],
    )

    assert record.business_approval_status == "preferred"
    assert "policy" in record.supported_option_kinds


def test_source_record_supports_official_operational_source() -> None:
    record = SourceRecord(
        source_id="amtrak-service-alerts",
        provider_name="Amtrak",
        display_name="Amtrak Service Alerts",
        category="official_operational",
        coverage_scope="national",
        supported_option_kinds=["rail"],
        trust_signals=SourceTrustSignals(
            freshness_days=0,
            freshness_confidence=1.0,
            commerciality=0.3,
            editorial_independence=0.4,
            operational_reliability=0.9,
            review_consistency=0.5,
        ),
    )

    assert record.category == "official_operational"
    assert record.trust_signals.operational_reliability == 0.9


def test_source_record_rejects_invalid_category() -> None:
    try:
        SourceRecord(
            source_id="x",
            provider_name="Provider",
            display_name="Display",
            category="blogspam",
        )
    except ValueError as exc:
        assert "category" in str(exc)
    else:
        raise AssertionError("SourceRecord should reject unsupported categories")


def test_source_record_rejects_invalid_supported_option_kind() -> None:
    try:
        SourceRecord(
            source_id="x",
            provider_name="Provider",
            display_name="Display",
            category="ratings_reviews",
            supported_option_kinds=["spaceship"],
        )
    except ValueError as exc:
        assert "supported_option_kinds" in str(exc)
    else:
        raise AssertionError("SourceRecord should reject unsupported option kinds")


def test_source_trust_signals_reject_negative_freshness_days() -> None:
    try:
        SourceTrustSignals(freshness_days=-1)
    except ValueError as exc:
        assert "freshness_days" in str(exc)
    else:
        raise AssertionError("SourceTrustSignals should reject negative freshness days")
