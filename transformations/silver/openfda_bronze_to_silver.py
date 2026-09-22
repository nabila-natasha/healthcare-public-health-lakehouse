import argparse
import json
from pathlib import Path

import pandas as pd


EVENT_COLUMNS = [
    "safetyreportid",
    "transmissiondate",
    "receivedate",
    "receiptdate",
    "serious",
    "seriousnessdeath",
    "fulfillexpeditecriteria",
    "companynumb",
    "reportercountry",
    "reporterqualification",
    "senderorganization",
    "patientonsetage",
    "patientonsetageunit",
    "patientsex",
    "patientdeathdate",
]


def parse_json_array(value):
    if pd.isna(value) or not str(value).strip():
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON value: {value}") from exc

    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array.")

    return parsed


def transform(input_file: Path, output_dir: Path):
    df = pd.read_csv(
        input_file,
        dtype=str,
        keep_default_na=False,
    )

    if df.empty:
        raise ValueError("OpenFDA Bronze dataset is empty.")

    required_columns = EVENT_COLUMNS + [
        "reactions_json",
        "drugs_json",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required Bronze columns: {missing}"
        )

    input_count = len(df)

    # ------------------------------------------------------------------
    # Event-level Silver table
    # ------------------------------------------------------------------

    events = df[EVENT_COLUMNS].copy()

    # safetyreportid is the business identifier for the report.
    if events["safetyreportid"].eq("").any():
        raise ValueError("Found records with missing safetyreportid.")

    duplicate_count = events["safetyreportid"].duplicated().sum()

    if duplicate_count:
        raise ValueError(
            f"Found {duplicate_count} duplicate safetyreportid values."
        )

    # Convert numeric fields.
    numeric_columns = [
        "serious",
        "seriousnessdeath",
        "fulfillexpeditecriteria",
        "patientonsetage",
        "patientsex",
        "reporterqualification",
    ]

    for column in numeric_columns:
        events[column] = pd.to_numeric(
            events[column],
            errors="coerce",
        )

    # Preserve source lineage.
    events["source"] = "openFDA"
    events["source_dataset"] = "FDA adverse event data"

    # ------------------------------------------------------------------
    # Reaction child table
    # ------------------------------------------------------------------

    reaction_rows = []

    for _, row in df.iterrows():
        reactions = parse_json_array(row["reactions_json"])

        for index, reaction in enumerate(reactions, start=1):
            reaction_rows.append(
                {
                    "safetyreportid": row["safetyreportid"],
                    "reaction_index": index,
                    "reactionmeddrapt": reaction.get(
                        "reactionmeddrapt"
                    ),
                    "reactionmeddraversionpt": reaction.get(
                        "reactionmeddraversionpt"
                    ),
                }
            )

    reactions = pd.DataFrame(
        reaction_rows,
        columns=[
            "safetyreportid",
            "reaction_index",
            "reactionmeddrapt",
            "reactionmeddraversionpt",
        ],
    )

    # ------------------------------------------------------------------
    # Drug child table
    # ------------------------------------------------------------------

    drug_rows = []

    for _, row in df.iterrows():
        drugs = parse_json_array(row["drugs_json"])

        for index, drug in enumerate(drugs, start=1):
            drug_rows.append(
                {
                    "safetyreportid": row["safetyreportid"],
                    "drug_index": index,
                    "drugcharacterization": drug.get(
                        "drugcharacterization"
                    ),
                    "medicinalproduct": drug.get(
                        "medicinalproduct"
                    ),
                    "drugbatchnumb": drug.get(
                        "drugbatchnumb"
                    ),
                    "drugauthorizationnumb": drug.get(
                        "drugauthorizationnumb"
                    ),
                    "drugstructuredosagenumb": drug.get(
                        "drugstructuredosagenumb"
                    ),
                    "drugstructuredosageunit": drug.get(
                        "drugstructuredosageunit"
                    ),
                    "drugdosagetext": drug.get(
                        "drugdosagetext"
                    ),
                    "drugadministrationroute": drug.get(
                        "drugadministrationroute"
                    ),
                    "drugindication": drug.get(
                        "drugindication"
                    ),
                    "drugstartdateformat": drug.get(
                        "drugstartdateformat"
                    ),
                    "drugstartdate": drug.get(
                        "drugstartdate"
                    ),
                }
            )

    drugs = pd.DataFrame(
        drug_rows,
        columns=[
            "safetyreportid",
            "drug_index",
            "drugcharacterization",
            "medicinalproduct",
            "drugbatchnumb",
            "drugauthorizationnumb",
            "drugstructuredosagenumb",
            "drugstructuredosageunit",
            "drugdosagetext",
            "drugadministrationroute",
            "drugindication",
            "drugstartdateformat",
            "drugstartdate",
        ],
    )

    # ------------------------------------------------------------------
    # Write Silver Parquet
    # ------------------------------------------------------------------

    output_dir.mkdir(parents=True, exist_ok=True)

    events.to_parquet(
        output_dir / "adverse_events.parquet",
        index=False,
    )

    reactions.to_parquet(
        output_dir / "adverse_event_reactions.parquet",
        index=False,
    )

    drugs.to_parquet(
        output_dir / "adverse_event_drugs.parquet",
        index=False,
    )

    print("=== OpenFDA Bronze → Silver ===")
    print(f"Bronze event records : {input_count}")
    print(f"Silver event records : {len(events)}")
    print(f"Reaction records     : {len(reactions)}")
    print(f"Drug records         : {len(drugs)}")
    print(f"Duplicate report IDs : {duplicate_count}")
    print(f"Output directory     : {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Transform OpenFDA Bronze CSV into Silver Parquet tables."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="OpenFDA Bronze CSV.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Silver output directory.",
    )

    args = parser.parse_args()

    transform(
        Path(args.input),
        Path(args.output),
    )


if __name__ == "__main__":
    main()
