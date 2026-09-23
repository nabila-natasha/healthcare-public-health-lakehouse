import argparse
from pathlib import Path

import pandas as pd


def build_features(events_path, reactions_path, drugs_path, output_path):
    events = pd.read_parquet(events_path)
    reactions = pd.read_parquet(reactions_path)
    drugs = pd.read_parquet(drugs_path)

    # One row per adverse-event report
    features = events.copy()

    # Aggregate child tables to report level
    reaction_counts = (
        reactions.groupby("safetyreportid")
        .size()
        .rename("number_of_reactions")
    )

    drug_counts = (
        drugs.groupby("safetyreportid")
        .size()
        .rename("number_of_drugs")
    )

    features = features.merge(
        reaction_counts,
        on="safetyreportid",
        how="left",
    )

    features = features.merge(
        drug_counts,
        on="safetyreportid",
        how="left",
    )

    features["number_of_reactions"] = (
        features["number_of_reactions"].fillna(0).astype(int)
    )

    features["number_of_drugs"] = (
        features["number_of_drugs"].fillna(0).astype(int)
    )

    # Date-derived features
    transmission_date = pd.to_datetime(
        features["transmissiondate"],
        format="%Y%m%d",
        errors="coerce",
    )

    received_date = pd.to_datetime(
        features["receivedate"],
        format="%Y%m%d",
        errors="coerce",
    )

    features["transmission_year"] = transmission_date.dt.year
    features["transmission_month"] = transmission_date.dt.month

    features["reporting_delay_days"] = (
        transmission_date - received_date
    ).dt.days

    # Keep a simple, interpretable target.
    features["target_serious"] = (features["serious"].astype(int) == 1).astype(int)

    # Remove identifiers and fields that may leak the target.
    model_features = features[
        [
            "safetyreportid",
            "patientonsetage",
            "patientonsetageunit",
            "patientsex",
            "reportercountry",
            "reporterqualification",
            "number_of_reactions",
            "number_of_drugs",
            "transmission_year",
            "transmission_month",
            "reporting_delay_days",
            "target_serious",
        ]
    ].copy()

    # Useful ratio feature.
    model_features["drug_reaction_ratio"] = (
        model_features["number_of_drugs"]
        / model_features["number_of_reactions"].replace(0, pd.NA)
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model_features.to_parquet(output_path, index=False)

    print("=== OpenFDA ML Feature Engineering ===")
    print(f"Input adverse events : {len(events)}")
    print(f"Reaction records     : {len(reactions)}")
    print(f"Drug records         : {len(drugs)}")
    print(f"ML feature rows      : {len(model_features)}")
    print(f"ML feature columns   : {len(model_features.columns)}")
    print(f"Output               : {output_path}")
    print()
    print("Target distribution:")
    print(model_features["target_serious"].value_counts(dropna=False))
    print()
    print("Output columns:")
    print(list(model_features.columns))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--events", required=True)
    parser.add_argument("--reactions", required=True)
    parser.add_argument("--drugs", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    build_features(
        args.events,
        args.reactions,
        args.drugs,
        args.output,
    )
