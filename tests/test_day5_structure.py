from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_transformation_scripts_exist():
    expected_scripts = [
        "transformations/silver/cdc_bronze_to_silver.py",
        "transformations/silver/openfda_bronze_to_silver.py",
        "transformations/gold/cdc_silver_to_gold.py",
        "transformations/gold/openfda_silver_to_gold.py",
    ]

    for script in expected_scripts:
        path = REPOSITORY_ROOT / script
        assert path.exists(), f"Missing transformation script: {script}"


def test_day5_validation_script_exists():
    path = REPOSITORY_ROOT / "scripts/silver_gold_validations.py"

    assert path.exists(), "Missing Silver/Gold validation script"


def test_medallion_directories_exist():
    expected_directories = [
        "transformations/silver",
        "transformations/gold",
    ]

    for directory in expected_directories:
        path = REPOSITORY_ROOT / directory
        assert path.is_dir(), f"Missing transformation directory: {directory}"


def test_day5_documentation_exists():
    path = REPOSITORY_ROOT / "docs/day5-medallion-processing.md"

    assert path.exists(), "Missing Day 5 documentation"
