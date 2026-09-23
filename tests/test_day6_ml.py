from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_day6_required_files_exist():
    required_files = [
        "docs/day6-analytics-ml.md",
        "notebooks/Day6_OpenFDA_ML.ipynb",
        "transformations/ml/openfda_features.py",
    ]

    for relative_path in required_files:
        path = REPO_ROOT / relative_path
        assert path.exists(), f"Missing required Day 6 file: {relative_path}"


def test_day6_ml_transformation_contains_expected_features():
    path = REPO_ROOT / "transformations/ml/openfda_features.py"
    source = path.read_text(encoding="utf-8")

    expected_features = [
        "number_of_reactions",
        "number_of_drugs",
        "transmission_year",
        "transmission_month",
        "reporting_delay_days",
        "target_serious",
        "drug_reaction_ratio",
    ]

    for feature in expected_features:
        assert feature in source, (
            f"Expected ML feature not found in transformation: {feature}"
        )


def test_day6_leakage_controls_are_documented():
    path = REPO_ROOT / "docs/day6-analytics-ml.md"
    documentation = path.read_text(encoding="utf-8").lower()

    required_items = [
        "leakage",
        "seriousnessdeath",
        "fulfillexpeditecriteria",
        "patientdeathdate",
        "companynumb",
    ]

    for item in required_items:
        assert item in documentation, (
            f"Expected leakage-control documentation missing: {item}"
        )


def test_day6_documentation_contains_recorded_model_results():
    path = REPO_ROOT / "docs/day6-analytics-ml.md"
    documentation = path.read_text(encoding="utf-8")

    expected_results = [
        "| Accuracy  | 0.7800 |",
        "| Precision | 0.7831 |",
        "| Recall    | 0.7143 |",
        "| F1        | 0.7471 |",
        "| ROC-AUC   | 0.8759 |",
        "| PR-AUC    | 0.8803 |",
    ]

    for result in expected_results:
        assert result in documentation, (
            f"Recorded Day 6 model result missing from documentation: {result}"
        )


def test_day6_documentation_contains_confusion_matrix_results():
    path = REPO_ROOT / "docs/day6-analytics-ml.md"
    documentation = path.read_text(encoding="utf-8")

    expected_values = [
        "True Negative  = 91",
        "False Positive = 18",
        "False Negative = 26",
        "True Positive   = 65",
    ]

    for value in expected_values:
        assert value in documentation, (
            f"Confusion matrix result missing from documentation: {value}"
        )


def test_day6_documentation_contains_downstream_serving_layer():
    path = REPO_ROOT / "docs/day6-analytics-ml.md"
    documentation = path.read_text(encoding="utf-8")

    required_items = [
        "openfda_ml_predictions.parquet",
        "dbo.vw_openfda_ml_predictions",
        "Synapse Serverless",
        "Power BI",
    ]

    for item in required_items:
        assert item in documentation, (
            f"Day 6 downstream serving item missing from documentation: {item}"
        )
