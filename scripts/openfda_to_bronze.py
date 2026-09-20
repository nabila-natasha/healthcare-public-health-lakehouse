import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Transform openFDA adverse-event JSON into Bronze CSV."
    )
    parser.add_argument("--input", required=True, help="Path to RAW openFDA JSON")
    parser.add_argument("--output", required=True, help="Path to Bronze CSV")
    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    with input_file.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    records = data.get("results", [])

    if not records:
        raise ValueError("No records found in openFDA response.")

    columns = [
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
        "reactions_json",
        "drugs_json",
    ]

    seen_ids = set()
    rows = []

    for record in records:
        safetyreportid = record.get("safetyreportid")

        if not safetyreportid:
            raise ValueError("Record is missing safetyreportid.")

        if safetyreportid in seen_ids:
            raise ValueError(f"Duplicate safetyreportid: {safetyreportid}")

        seen_ids.add(safetyreportid)

        primarysource = record.get("primarysource") or {}
        sender = record.get("sender") or {}
        patient = record.get("patient") or {}
        patientdeath = patient.get("patientdeath") or {}

        reactions = patient.get("reaction") or []
        drugs = patient.get("drug") or []

        rows.append(
            {
                "safetyreportid": safetyreportid,
                "transmissiondate": record.get("transmissiondate"),
                "receivedate": record.get("receivedate"),
                "receiptdate": record.get("receiptdate"),
                "serious": record.get("serious"),
                "seriousnessdeath": record.get("seriousnessdeath"),
                "fulfillexpeditecriteria": record.get(
                    "fulfillexpeditecriteria"
                ),
                "companynumb": record.get("companynumb"),
                "reportercountry": primarysource.get("reportercountry"),
                "reporterqualification": primarysource.get("qualification"),
                "senderorganization": sender.get("senderorganization"),
                "patientonsetage": patient.get("patientonsetage"),
                "patientonsetageunit": patient.get("patientonsetageunit"),
                "patientsex": patient.get("patientsex"),
                "patientdeathdate": patientdeath.get("patientdeathdate"),
                "reactions_json": json.dumps(
                    reactions,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "drugs_json": json.dumps(
                    drugs,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print("=== openFDA Bronze Transformation ===")
    print(f"Input records : {len(records)}")
    print(f"Output records: {len(rows)}")
    print(f"Unique IDs    : {len(seen_ids)}")
    print(f"Output file   : {output_file}")
    print(f"Output size   : {output_file.stat().st_size} bytes")


if __name__ == "__main__":
    main()
