import argparse
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Transform OpenFDA Silver into Gold analytical aggregates."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="OpenFDA Silver events Parquet file.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="OpenFDA Gold Parquet file.",
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
        raise ValueError("OpenFDA Silver events dataset is empty.")

    required = [
        "safetyreportid",
        "transmissiondate",
        "reportercountry",
        "serious",
        "seriousnessdeath",
        "fulfillexpeditecriteria",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required Gold columns: {missing}"
        )

    # Parse transmission date.
    df["transmission_date"] = pd.to_datetime(
        df["transmissiondate"],
        format="%Y%m%d",
        errors="coerce",
    )

    # Treat blank country values as UNKNOWN rather than dropping records.
    df["reporter_country"] = (
        df["reportercountry"]
        .replace("", pd.NA)
        .fillna("UNKNOWN")
    )

    # Explicit numeric conversion.
    for column in [
        "serious",
        "seriousnessdeath",
        "fulfillexpeditecriteria",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # Gold grain:
    # one row per reporter country and transmission date.
    gold = (
        df.groupby(
            ["reporter_country", "transmission_date"],
            as_index=False,
        )
        .agg(
            adverse_event_reports=(
                "safetyreportid",
                "nunique",
            ),
            serious_reports=(
                "serious",
                lambda x: (x == 1).sum(),
            ),
            death_reports=(
                "seriousnessdeath",
                lambda x: (x == 1).sum(),
            ),
            expedited_reports=(
                "fulfillexpeditecriteria",
                lambda x: (x == 1).sum(),
            ),
        )
    )

    # Derived analytical indicators.
    gold["serious_report_pct"] = (
        gold["serious_reports"]
        .div(gold["adverse_event_reports"])
        .mul(100)
    )

    gold["death_report_pct"] = (
        gold["death_reports"]
        .div(gold["adverse_event_reports"])
        .mul(100)
    )

    gold["expedited_report_pct"] = (
        gold["expedited_reports"]
        .div(gold["adverse_event_reports"])
        .mul(100)
    )

    gold = gold.sort_values(
        ["transmission_date", "reporter_country"]
    ).reset_index(drop=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    gold.to_parquet(
        output_file,
        index=False,
    )

    print("=== OpenFDA Silver → Gold ===")
    print(f"Silver records : {len(df)}")
    print(f"Gold records   : {len(gold)}")
    print(
        f"Countries      : "
        f"{gold['reporter_country'].nunique()}"
    )
    print(f"Output file    : {output_file}")
    print(f"Output size    : {output_file.stat().st_size} bytes")


if __name__ == "__main__":
    main()
