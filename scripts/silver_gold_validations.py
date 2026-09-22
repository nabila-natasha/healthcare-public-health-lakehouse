from pathlib import Path

import pandas as pd


BASE = Path("tmp/day5")

CDC_SILVER = BASE / "cdc_silver/cdc_silver.parquet"
CDC_GOLD = BASE / "cdc_gold/cdc_gold.parquet"

OPENFDA_EVENTS = BASE / "openfda_silver/adverse_events.parquet"
OPENFDA_REACTIONS = BASE / "openfda_silver/adverse_event_reactions.parquet"
OPENFDA_DRUGS = BASE / "openfda_silver/adverse_event_drugs.parquet"
OPENFDA_GOLD = BASE / "openfda_gold/openfda_gold.parquet"


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")


def check_no_nulls(
    df: pd.DataFrame,
    columns: list[str],
    dataset_name: str,
) -> None:
    null_counts = df[columns].isna().sum()
    failures = null_counts[null_counts > 0]

    if not failures.empty:
        raise AssertionError(
            f"{dataset_name}: null values found:\n{failures}"
        )


def validate_cdc() -> None:
    print("\n===== CDC SILVER =====")

    silver = pd.read_parquet(CDC_SILVER)

    print(f"Rows: {len(silver)}")
    print(f"Columns: {len(silver.columns)}")
    print(f"States: {silver['state'].nunique()}")
    print(
        "Duplicate event IDs:",
        silver["event_id"].duplicated().sum(),
    )

    assert len(silver) == 1000
    assert silver["event_id"].nunique() == 1000
    assert silver["state"].nunique() == 60

    check_no_nulls(
        silver,
        [
            "event_id",
            "event_time",
            "ingestion_time",
            "source",
            "source_dataset_id",
            "state",
            "start_date",
            "end_date",
        ],
        "CDC Silver",
    )

    print("CDC Silver: PASS")

    print("\n===== CDC GOLD =====")

    gold = pd.read_parquet(CDC_GOLD)

    duplicate_grain = gold.duplicated(
        subset=["state", "start_date", "end_date"]
    ).sum()

    print(f"Rows: {len(gold)}")
    print(f"Columns: {len(gold.columns)}")
    print(f"States: {gold['state'].nunique()}")
    print(f"Duplicate grain: {duplicate_grain}")

    assert len(gold) == 1000
    assert gold["state"].nunique() == 60
    assert duplicate_grain == 0

    check_no_nulls(
        gold,
        [
            "state",
            "start_date",
            "end_date",
            "total_cases",
            "new_cases",
            "total_deaths",
            "new_deaths",
            "historic_cases",
            "historic_deaths",
            "source_event_count",
        ],
        "CDC Gold",
    )

    silver_count = len(silver)
    gold_source_count = gold["source_event_count"].sum()

    print("\n===== CDC RECONCILIATION =====")
    print(f"Silver source events: {silver_count}")
    print(f"Gold source events: {gold_source_count}")

    assert gold_source_count == silver_count

    print("CDC reconciliation: PASS")
    print("CDC Gold: PASS")


def validate_openfda() -> None:
    print("\n===== OPENFDA SILVER =====")

    events = pd.read_parquet(OPENFDA_EVENTS)
    reactions = pd.read_parquet(OPENFDA_REACTIONS)
    drugs = pd.read_parquet(OPENFDA_DRUGS)

    duplicate_ids = events["safetyreportid"].duplicated().sum()

    print(f"Adverse events: {len(events)}")
    print(f"Reaction records: {len(reactions)}")
    print(f"Drug records: {len(drugs)}")
    print(f"Duplicate report IDs: {duplicate_ids}")

    assert len(events) == 100
    assert events["safetyreportid"].nunique() == 100
    assert duplicate_ids == 0
    assert len(reactions) == 247
    assert len(drugs) == 265

    check_no_nulls(
        events,
        ["safetyreportid"],
        "openFDA Silver events",
    )

    print("openFDA Silver: PASS")

    print("\n===== OPENFDA GOLD =====")

    gold = pd.read_parquet(OPENFDA_GOLD)

    duplicate_grain = gold.duplicated(
        subset=["reporter_country", "transmission_date"]
    ).sum()

    print(f"Rows: {len(gold)}")
    print(f"Columns: {len(gold.columns)}")
    print(f"Countries: {gold['reporter_country'].nunique()}")
    print(f"Duplicate grain: {duplicate_grain}")

    assert len(gold) == 15
    assert gold["reporter_country"].nunique() == 11
    assert duplicate_grain == 0

    check_no_nulls(
        gold,
        [
            "reporter_country",
            "transmission_date",
            "adverse_event_reports",
            "serious_reports",
            "death_reports",
            "expedited_reports",
            "serious_report_pct",
            "death_report_pct",
            "expedited_report_pct",
        ],
        "openFDA Gold",
    )

    silver_reports = events["safetyreportid"].nunique()
    gold_reports = gold["adverse_event_reports"].sum()

    print("\n===== OPENFDA RECONCILIATION =====")
    print(f"Silver report IDs: {silver_reports}")
    print(f"Gold report count: {gold_reports}")

    assert silver_reports == gold_reports

    print("openFDA reconciliation: PASS")
    print("openFDA Gold: PASS")


def main() -> None:
    print("=" * 72)
    print("SILVER / GOLD VALIDATION")
    print("=" * 72)

    required_files = [
        CDC_SILVER,
        CDC_GOLD,
        OPENFDA_EVENTS,
        OPENFDA_REACTIONS,
        OPENFDA_DRUGS,
        OPENFDA_GOLD,
    ]

    for path in required_files:
        require_file(path)

    print("\nAll expected Parquet files found.")

    validate_cdc()
    validate_openfda()

    print("\n" + "=" * 72)
    print("SILVER / GOLD VALIDATION: PASS")
    print("=" * 72)


if __name__ == "__main__":
    main()
