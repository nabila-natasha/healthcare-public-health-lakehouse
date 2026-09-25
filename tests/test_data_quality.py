import hashlib

import pandas as pd
import pytest


def check_no_nulls(df, columns, dataset_name):
    null_counts = df[columns].isna().sum()
    failures = null_counts[null_counts > 0]

    if not failures.empty:
        raise AssertionError(
            f"{dataset_name}: null values found:\\n{failures}"
        )



def make_cdc_event_id(
    state: str,
    start_date: str,
    end_date: str,
) -> str:
    business_key = f"{state}|{start_date}|{end_date}"
    return hashlib.sha256(
        business_key.encode("utf-8")
    ).hexdigest()


def test_cdc_event_id_is_deterministic_sha256():
    state = "DC"
    start_date = "2020-04-16T00:00:00.000"
    end_date = "2020-04-22T00:00:00.000"

    event_id = make_cdc_event_id(
        state,
        start_date,
        end_date,
    )

    expected = (
        "003cf978ff7aa18d7e9410b8df890638"
        "cbe4a9ac9af6f0de5a241ed3492971b6"
    )

    assert event_id == expected
    assert len(event_id) == 64


def test_cdc_event_id_changes_when_business_key_changes():
    event_id_1 = make_cdc_event_id(
        "DC",
        "2020-04-16T00:00:00.000",
        "2020-04-22T00:00:00.000",
    )

    event_id_2 = make_cdc_event_id(
        "DC",
        "2020-04-17T00:00:00.000",
        "2020-04-23T00:00:00.000",
    )

    assert event_id_1 != event_id_2


def test_required_cdc_fields_have_no_nulls():
    df = pd.DataFrame(
        {
            "event_id": [
                make_cdc_event_id(
                    "DC",
                    "2020-04-16T00:00:00.000",
                    "2020-04-22T00:00:00.000",
                )
            ],
            "event_time": ["2020-04-23T00:00:00.000"],
            "ingestion_time": ["2026-09-21T05:42:36.901364+00:00"],
            "source": ["cdc_historical_replay"],
            "source_dataset_id": ["pwn4-m3yp"],
            "state": ["DC"],
            "start_date": ["2020-04-16T00:00:00.000"],
            "end_date": ["2020-04-22T00:00:00.000"],
        }
    )

    check_no_nulls(
        df,
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


def test_required_field_null_fails_validation():
    df = pd.DataFrame(
        {
            "event_id": [
                make_cdc_event_id(
                    "DC",
                    "2020-04-16T00:00:00.000",
                    "2020-04-22T00:00:00.000",
                ),
                None,
            ],
            "event_time": [
                "2020-04-23T00:00:00.000",
                "2020-04-24T00:00:00.000",
            ],
        }
    )

    with pytest.raises(AssertionError, match="null values found"):
        check_no_nulls(
            df,
            ["event_id", "event_time"],
            "CDC Silver",
        )


def test_cdc_event_id_must_be_unique():
    event_id_1 = make_cdc_event_id(
        "DC",
        "2020-04-16T00:00:00.000",
        "2020-04-22T00:00:00.000",
    )

    event_id_2 = make_cdc_event_id(
        "CA",
        "2020-04-16T00:00:00.000",
        "2020-04-22T00:00:00.000",
    )

    df = pd.DataFrame(
        {
            "event_id": [event_id_1, event_id_2],
        }
    )

    assert df["event_id"].duplicated().sum() == 0
    assert df["event_id"].nunique() == len(df)


def test_cdc_duplicate_event_id_is_detected():
    event_id = make_cdc_event_id(
        "DC",
        "2020-04-16T00:00:00.000",
        "2020-04-22T00:00:00.000",
    )

    df = pd.DataFrame(
        {
            "event_id": [event_id, event_id],
        }
    )

    assert df["event_id"].duplicated().sum() == 1
    assert df["event_id"].nunique() == 1


def test_cdc_gold_grain_must_be_unique():
    df = pd.DataFrame(
        {
            "state": ["CA", "CA", "TX"],
            "start_date": [
                "2023-01-01",
                "2023-01-01",
                "2023-01-01",
            ],
            "end_date": [
                "2023-01-07",
                "2023-01-07",
                "2023-01-07",
            ],
        }
    )

    duplicate_grain = df.duplicated(
        subset=["state", "start_date", "end_date"]
    ).sum()

    assert duplicate_grain == 1


def test_cdc_gold_reconciles_to_silver_source_events():
    silver = pd.DataFrame(
        {
            "event_id": [
                make_cdc_event_id(
                    "DC",
                    "2020-04-16T00:00:00.000",
                    "2020-04-22T00:00:00.000",
                ),
                make_cdc_event_id(
                    "CA",
                    "2020-04-16T00:00:00.000",
                    "2020-04-22T00:00:00.000",
                ),
                make_cdc_event_id(
                    "TX",
                    "2020-04-16T00:00:00.000",
                    "2020-04-22T00:00:00.000",
                ),
            ]
        }
    )

    gold = pd.DataFrame(
        {
            "state": ["DC", "CA", "TX"],
            "source_event_count": [1, 1, 1],
        }
    )

    assert gold["source_event_count"].sum() == len(silver)


def test_openfda_safetyreportid_must_be_unique():
    events = pd.DataFrame(
        {
            "safetyreportid": [
                "100001",
                "100002",
                "100003",
            ]
        }
    )

    assert events["safetyreportid"].duplicated().sum() == 0
    assert events["safetyreportid"].nunique() == len(events)


def test_openfda_duplicate_safetyreportid_is_detected():
    events = pd.DataFrame(
        {
            "safetyreportid": [
                "100001",
                "100002",
                "100001",
            ]
        }
    )

    assert events["safetyreportid"].duplicated().sum() == 1
    assert events["safetyreportid"].nunique() < len(events)


def test_ml_target_is_binary():
    features = pd.DataFrame(
        {
            "target_serious": [0, 1, 0, 1, 1],
        }
    )

    assert set(features["target_serious"].unique()).issubset({0, 1})


def test_ml_leakage_fields_are_not_model_features():
    model_features = {
        "patientonsetage",
        "patientsex",
        "reportercountry",
        "number_of_reactions",
        "number_of_drugs",
        "reporting_delay_days",
        "drug_reaction_ratio",
    }

    excluded_leakage_fields = {
        "serious",
        "seriousnessdeath",
        "fulfillexpeditecriteria",
        "patientdeathdate",
        "companynumb",
    }

    assert model_features.isdisjoint(excluded_leakage_fields)
