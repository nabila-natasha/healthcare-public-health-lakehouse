import argparse
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Transform CDC Silver into Gold analytical aggregates."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input CDC Silver Parquet file.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output CDC Gold Parquet file.",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        raise FileNotFoundError(
            f"Input file does not exist: {input_file}"
        )

    df = pd.read_parquet(input_file)

    if df.empty:
        raise ValueError("CDC Silver dataset is empty.")

    required_columns = [
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

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required Gold columns: {missing}"
        )

    # Gold grain:
    # one row per state and reporting period.
    gold = (
        df.groupby(
            ["state", "start_date", "end_date"],
            as_index=False,
        )
        .agg(
            total_cases=("tot_cases", "max"),
            new_cases=("new_cases", "sum"),
            total_deaths=("tot_deaths", "max"),
            new_deaths=("new_deaths", "sum"),
            historic_cases=("new_historic_cases", "sum"),
            historic_deaths=("new_historic_deaths", "sum"),
            source_event_count=("event_id", "nunique"),
        )
    )

    # Derived analytical metric.
    gold["cumulative_death_case_ratio_pct"] = (
        gold["total_deaths"]
        .div(gold["total_cases"])
        .where(gold["total_cases"] > 0)
        .mul(100)
    )

    gold = gold.sort_values(
        ["state", "start_date", "end_date"]
    ).reset_index(drop=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    gold.to_parquet(
        output_file,
        index=False,
    )

    print("=== CDC Silver → Gold ===")
    print(f"Silver records : {len(df)}")
    print(f"Gold records   : {len(gold)}")
    print(f"States         : {gold['state'].nunique()}")
    print(f"Output file    : {output_file}")
    print(f"Output size    : {output_file.stat().st_size} bytes")


if __name__ == "__main__":
    main()
