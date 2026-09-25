from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_day7_serving_documentation_exists():
    required_docs = [
        "docs/day7-power-bi-serving.md",
        "docs/data-sources.md",
        "docs/data-contract.md",
    ]

    for relative_path in required_docs:
        assert (ROOT / relative_path).exists(), (
            f"Required documentation is missing: {relative_path}"
        )


def test_day7_ml_outputs_are_documented():
    day7_doc = ROOT / "docs/day7-power-bi-serving.md"
    content = day7_doc.read_text(encoding="utf-8")

    required_terms = [
        "vw_openfda_ml_predictions",
        "vw_openfda_feature_importance",
        "vw_openfda_anomalies",
        "FACT_OPENFDA_FEATURE_IMPORTANCE",
        "FACT_OPENFDA_ANOMALIES",
        "Isolation Forest",
        "XGBoost",
    ]

    for term in required_terms:
        assert term in content, (
            f"Expected Day 7 serving reference not found: {term}"
        )


def test_day7_cdc_limitation_is_explicitly_documented():
    day7_doc = ROOT / "docs/day7-power-bi-serving.md"
    content = day7_doc.read_text(encoding="utf-8").lower()

    required_qualifications = [
        "archived historical surveillance data",
        "near-real-time arrival",
        "does not represent a genuine real-time cdc feed",
    ]

    for qualification in required_qualifications:
        assert qualification in content, (
            f"Required CDC limitation is missing from Day 7 documentation: "
            f"{qualification}"
        )


def test_day7_clinical_scope_is_explicitly_qualified():
    day7_doc = ROOT / "docs/day7-power-bi-serving.md"
    content = day7_doc.read_text(encoding="utf-8").lower()

    assert "analytical dashboard rather than a live clinical monitoring system" in content
    assert "avoids presenting model outputs as clinical decisions" in content
