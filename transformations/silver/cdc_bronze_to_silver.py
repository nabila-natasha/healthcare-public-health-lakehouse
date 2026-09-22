import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "event_id",
    "event_time",
    "ingestion_time",
    "source",
    "source_dataset_id",
    "state",
    "start_date",
    "end_date",
    "tot_cases",
    "new_cases",
    "tot_deaths",
    "new_deaths",
    "new_historic_cases",
    "new_historic_deaths",
]


NUMERIC_COLUMNS = [
    "tot_cases",
    "new_cases",
    "tot_deaths",
    "new_deaths",
    "new_historic_cases",
    "new_historic_deaths",
]


DATE_COLUMNS = [
    "event_time",
    "ingestion_time",
    "processed_time",
]


def load_json_files(input_dir: Path) -> list[dict]:
    records = []

    for path in sorted(input_dir.rglob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            records.append(json.load(f))

    return records


def transform(records: list[dict]) -> pd.DataFrame:
    rows = []

    for record in records:
        payload = record.get("payload") or {}

        row = {
            "event_id": record.get("event_id"),
            "event_time": record.get("event_time"),
            "ingestion_time": record.get("ingestion_time"),
            "processed_time": record.get("processed_time"),
            "source": record.get("source"),
            "source_dataset_id": record.get("source_dataset_id"),
            "state": payload.get("state"),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "tot_cases": payload.get("tot_cases"),
            "new_cases": payload.get("new_cases"),
            "tot_deaths": payload.get("tot_deaths"),
            "new_deaths": payload.get("new_deaths"),
            "new_historic_cases": payload.get("new_historic_cases"),
            "new_historic_deaths": payload.get("new_historic_deaths"),
        }

        rows.append(row)

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("No CDC Bronze records found.")

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required Silver columns: {missing_columns}"
        )

    # Remove duplicate deliveries using the deterministic event ID.
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["event_id"], keep="first")
    duplicate_count = before_dedup - len(df)

    # Parse timestamps and dates.
    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
            utc=True,
        )

    df["start_date"] = pd.to_datetime(
        df["start_date"],
        errors="coerce",
    ).dt.date

    df["end_date"] = pd.to_datetime(
        df["end_date"],
        errors="coerce",
    ).dt.date

    # Convert CDC numeric fields from strings to numeric values.
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # Required-field validation.
    required_for_silver = [
        "event_id",
        "event_time",
        "ingestion_time",
        "source",
        "source_dataset_id",
        "state",
        "start_date",
        "end_date",
    ]

    invalid_required = df[required_for_silver].isna().any(axis=1)

    if invalid_required.any():
        invalid_count = int(invalid_required.sum())
        raise ValueError(
            f"{invalid_count} records failed required-field validation."
        )

    # Keep only the intended Silver schema.
    columns = [
        "event_id",
        "event_time",
        "ingestion_time",
        "processed_time",
        "source",
        "source_dataset_id",
        "state",
        "start_date",
        "end_date",
        "tot_cases",
        "new_cases",
        "tot_deaths",
        "new_deaths",
        "new_historic_cases",
        "new_historic_deaths",
    ]

    df = df[columns]

    print("=== CDC Bronze → Silver ===")
    print(f"Input records       : {before_dedup}")
    print(f"Duplicate deliveries: {duplicate_count}")
    print(f"Silver records      : {len(df)}")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Transform CDC Bronze JSON into Silver Parquet."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Local directory containing downloaded CDC Bronze JSON files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output Parquet file.",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_file = Path(args.output)

    if not input_dir.exists():
        raise FileNotFoundError(
            f"Input directory does not exist: {input_dir}"
        )

    records = load_json_files(input_dir)
    df = transform(records)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_file, index=False)

    print(f"Output file         : {output_file}")
    print(f"Output size         : {output_file.stat().st_size} bytes")


if __name__ == "__main__":
    main()
