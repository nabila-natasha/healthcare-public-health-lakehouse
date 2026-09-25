# Data Contracts

## Purpose

This document defines the logical data contracts used by the Healthcare Public Health Surveillance & Risk Analytics Lakehouse.

The contracts describe expected fields, identifiers, grain, and core validation rules across the CDC public-health streaming simulation and OpenFDA batch ingestion pipelines.

The project uses public and historical datasets only. It does not process real patient records or Protected Health Information (PHI).

---

# 1. CDC Public-Health Surveillance Event Contract

## Source

**Dataset:** Weekly United States COVID-19 Cases and Deaths by State - ARCHIVED

**Dataset ID:** `pwn4-m3yp`

The source contains historical public-health surveillance data.

The project replays historical records at an accelerated cadence to simulate near-real-time event arrival.

This is an event-ingestion simulation and does not represent a genuine real-time CDC feed.

## Event Envelope

Each Event Hubs message follows this logical structure:

| Field               | Type            | Required | Description                                           |
| ------------------- | --------------- | -------: | ----------------------------------------------------- |
| `event_id`          | string          |      Yes | Deterministic identifier for the logical source event |
| `event_time`        | datetime/string |      Yes | Source event time derived from `date_updated`         |
| `ingestion_time`    | datetime/string |      Yes | Time the event was received by the ingestion pipeline |
| `source`            | string          |      Yes | Source system identifier                              |
| `source_dataset_id` | string          |      Yes | CDC dataset identifier                                |
| `payload`           | object          |      Yes | Source surveillance record                            |

## CDC Payload

The payload contains the source surveillance attributes:

| Field                 | Description                                |
| --------------------- | ------------------------------------------ |
| `state`               | State or jurisdiction identifier           |
| `start_date`          | Start date of the reporting period         |
| `end_date`            | End date of the reporting period           |
| `tot_cases`           | Total reported cases                       |
| `new_cases`           | New reported cases                         |
| `tot_deaths`          | Total reported deaths                      |
| `new_deaths`          | New reported deaths                        |
| `new_historic_cases`  | Historical cases newly reported            |
| `new_historic_deaths` | Historical deaths newly reported           |
| `date_updated`        | Source update timestamp used as event time |

## Event ID

The producer generates a deterministic event identifier using:

```text
SHA256(state | start_date | end_date)
```

This allows duplicate delivery of the same logical source event to be identified.

## CDC Data-Quality Rules

The ingestion pipeline validates:

* Required event-envelope fields are present.
* `event_id` is not null.
* `event_time` is not null.
* `ingestion_time` is not null.
* Duplicate `event_id` values are detected.
* Malformed events are routed to quarantine.
* Late events are identified separately from duplicate deliveries.

## CDC Validation Result

The Day 4 validation run produced:

| Outcome                    | Records |
| -------------------------- | ------: |
| Events received            |   1,002 |
| Bronze records             |   1,000 |
| Quarantined invalid events |       1 |

The test data intentionally included duplicate delivery and malformed data to demonstrate validation and quarantine handling.

The duplicate delivery and malformed event are separate data-quality conditions and are not treated as interchangeable.

---

# 2. OpenFDA Batch Data Contract

## Source

**Source:** openFDA

**Dataset:** FDA adverse-event reports

**Access pattern:** REST API

**Ingestion pattern:** Batch

The source contains publicly available adverse-event reporting information.

These reports are useful for surveillance analytics but do not establish causality or adverse-event incidence.

## Ingestion Validation

The final ADF pagination validation retrieved:

* 4 API response pages
* 4,000 reports
* 4,000 unique `safetyreportid` values
* 0 duplicate report IDs

The 4,000-report result represents the validated ingestion batch.

The downstream Gold and ML development workflow used the project's 1,000-record working dataset.

This distinction prevents ingestion validation counts from being incorrectly presented as downstream transformation or ML dataset counts.

---

# 3. OpenFDA Silver Contract

The OpenFDA Silver layer normalizes the nested source report structure into three Parquet datasets.

## `adverse_events.parquet`

**Grain:** One row per adverse-event report.

Validation result:

* 1,000 rows
* 17 columns
* No duplicate `safetyreportid` values

Important attributes include:

* `safetyreportid`
* `receivedate`
* `transmissiondate`
* `serious`
* `patientonsetage`
* `patientonsetageunit`
* `patientsex`
* `reportercountry`
* `reporterqualification`

## `adverse_event_reactions.parquet`

**Grain:** One row per reaction associated with an adverse-event report.

Validation result:

* 2,749 rows
* 4 columns

`safetyreportid` provides the report-level linkage back to the adverse-event report.

## `adverse_event_drugs.parquet`

**Grain:** One row per drug associated with an adverse-event report.

Validation result:

* 3,079 rows
* 13 columns

`safetyreportid` provides the report-level linkage back to the adverse-event report.

---

# 4. OpenFDA Gold Contract

## Dataset

`openfda_gold.parquet`

## Grain

One row per:

```text
reporter_country + transmission_date
```

## Columns

| Column                  | Description                                         |
| ----------------------- | --------------------------------------------------- |
| `reporter_country`      | Reporter country                                    |
| `transmission_date`     | Report transmission date                            |
| `adverse_event_reports` | Number of adverse-event reports                     |
| `serious_reports`       | Number of reports classified as serious             |
| `death_reports`         | Number of reports containing a death-related signal |
| `expedited_reports`     | Number of expedited reports                         |
| `serious_report_pct`    | Serious reports as a percentage of reports          |
| `death_report_pct`      | Death-related reports as a percentage of reports    |
| `expedited_report_pct`  | Expedited reports as a percentage of reports        |

The Gold dataset is intended for analytical reporting and surveillance analytics.

It is not intended to establish causal relationships or clinical conclusions.

---

# 5. OpenFDA ML Feature Contract

## Dataset

`openfda_ml_features.parquet`

## Grain

One row per OpenFDA adverse-event report.

The feature dataset contains:

* 1,000 records
* 13 columns

## Feature Groups

### Patient and report attributes

* `patientonsetage`
* `patientonsetageunit`
* `patientsex`
* `reportercountry`
* `reporterqualification`

### Derived features

* `number_of_reactions`
* `number_of_drugs`
* `transmission_year`
* `transmission_month`
* `reporting_delay_days`
* `drug_reaction_ratio`

## Target

`target_serious`

The target is normalized from the source `serious` field.

The binary target distribution in the working dataset is:

| Target            | Records |
| ----------------- | ------: |
| Not Serious (`0`) |     546 |
| Serious (`1`)     |     454 |

## Leakage Controls

The following source fields are excluded from the model feature matrix:

* `serious`
* `seriousnessdeath`
* `fulfillexpeditecriteria`
* `patientdeathdate`
* `companynumb`

These fields are excluded because they can directly reveal or encode the target or introduce inappropriate information leakage.

`safetyreportid` is retained for traceability but excluded from the model feature matrix.

---

# 6. ML Prediction Contract

## Dataset

`openfda_ml_predictions.parquet`

## Grain

One row per scored OpenFDA report in the ML holdout set.

The current model evaluation contains:

* 200 holdout records
* 200 predictions

## Model

The seriousness-classification workflow uses XGBoost.

## Evaluation Results

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 78.00% |
| Precision | 78.31% |
| Recall    | 71.43% |
| F1        | 74.71% |
| ROC-AUC   | 87.59% |
| PR-AUC    | 88.03% |

The majority-class baseline accuracy was 54.5%.

These results describe the portfolio model evaluation on the current holdout dataset.

They should not be interpreted as clinical performance or production healthcare-model performance.

---

# 7. Feature Importance Contract

## Dataset

`openfda_feature_importance.parquet`

## Grain

One row per model feature.

| Column       | Type    | Description                      |
| ------------ | ------- | -------------------------------- |
| `feature`    | string  | Feature name after preprocessing |
| `importance` | numeric | XGBoost feature importance       |

Feature importance is used as a model diagnostic.

It does not establish causality.

For example, a high importance value for `reportercountry_US` is treated as a model/data signal requiring further investigation. It may reflect characteristics of the development sample, reporting practices, dataset composition, or other factors.

---

# 8. Anomaly Screening Contract

## Dataset

`openfda_anomalies.parquet`

## Grain

One row per OpenFDA report in the ML holdout set.

| Column               | Type    | Description                    |
| -------------------- | ------- | ------------------------------ |
| `safetyreportid`     | string  | OpenFDA report identifier      |
| `anomaly_prediction` | integer | Isolation Forest prediction    |
| `anomaly_score`      | numeric | Isolation Forest anomaly score |
| `is_anomaly`         | boolean | Final anomaly flag             |

## Current Validation

| Metric           | Result |
| ---------------- | -----: |
| Records screened |    200 |
| Records flagged  |     10 |
| Anomaly rate     |   5.0% |

The Isolation Forest configuration uses:

* `n_estimators = 200`
* `contamination = 0.05`
* `random_state = 42`
* `n_jobs = -1`

Isolation Forest identifies observations with unusual feature patterns for analytical review.

An anomaly flag does not indicate:

* fraud
* causality
* clinical risk
* patient harm

---

# 9. Serving Contract

The ML outputs are exposed through Synapse Serverless views for downstream analytical consumption.

## Synapse Views

| View                                | Purpose                          |
| ----------------------------------- | -------------------------------- |
| `dbo.vw_openfda_ml_predictions`     | Model prediction results         |
| `dbo.vw_openfda_analytics`          | OpenFDA analytical/Gold data     |
| `dbo.vw_openfda_feature_importance` | XGBoost feature importance       |
| `dbo.vw_openfda_anomalies`          | Isolation Forest anomaly results |

Power BI consumes these serving views through the `healthcare_analytics` Synapse database.

## Power BI Tables

The ML-specific serving layer includes:

* `FACT_OPENFDA_FEATURE_IMPORTANCE`
* `FACT_OPENFDA_ANOMALIES`

These are model-output tables rather than conventional business fact tables and are not joined through the project's core analytical relationships.

---

# 10. Data Quality and Quarantine Contract

The project distinguishes between:

### Valid data

Records that satisfy required structural and field-level validation rules and can proceed to the appropriate analytical layer.

### Duplicate delivery

A repeated delivery of an event that represents an already-seen logical source event.

Duplicate detection uses the deterministic CDC `event_id`.

### Late event

An event whose source event time is older than the current ingestion context.

Late events are detected and logged separately from duplicate delivery.

### Malformed event

An event that fails required structural validation.

Malformed CDC events are routed to the quarantine path instead of being written to Bronze.

This separation is intentional because duplicate delivery, late arrival, and malformed records represent different operational conditions.

---

# 11. Storage Contract

The canonical ADLS Gen2 filesystem is:

```text
healthcare
```

The main logical layers are:

```text
healthcare/
├── raw/
├── bronze/
├── silver/
├── gold/
└── ml/
```

## CDC

```text
raw/cdc/
bronze/cdc/
quarantine/cdc/
```

## OpenFDA

```text
raw/openfda/
bronze/openfda/
silver/openfda/
gold/openfda/
ml/openfda/
```

## ML outputs

```text
ml/openfda/
├── openfda_ml_features.parquet
├── openfda_ml_predictions.parquet
├── openfda_feature_importance.parquet
└── openfda_anomalies.parquet
```

Parquet is used for analytical datasets because it provides typed columns, columnar storage, compression, and compatibility with analytical engines.

---

# 12. Contract and Governance Principles

The project follows these principles:

1. Preserve source identifiers for traceability.
2. Separate event time from ingestion time.
3. Validate required fields before Bronze persistence.
4. Quarantine malformed events rather than silently dropping them.
5. Detect duplicate logical events using deterministic identifiers.
6. Treat late events separately from duplicate deliveries.
7. Use Parquet for typed analytical datasets.
8. Separate ingestion validation counts from downstream dataset counts.
9. Document ML leakage controls explicitly.
10. Treat model outputs as analytical signals rather than clinical decisions.
11. Avoid causal interpretation of observational reporting data.
12. Preserve limitations and data-quality assumptions in project documentation.
13. Do not commit API keys, connection strings, passwords, SAS tokens, or other secrets to source control.

---

# 13. Known Limitations

This document describes the portfolio implementation rather than a production healthcare platform.

Known limitations include:

* CDC data is archived historical surveillance data.
* Near-real-time behavior is simulated through accelerated replay.
* The CDC source is not a genuine real-time feed.
* OpenFDA reports are spontaneous adverse-event reporting data and are subject to reporting and selection biases.
* OpenFDA reports cannot by themselves establish causality or estimate adverse-event incidence.
* The project contains no PHI.
* The ML working dataset and holdout are limited in size.
* Model metrics should not be interpreted as clinical performance.
* Feature importance does not establish causality.
* Isolation Forest identifies unusual feature patterns but does not establish clinical risk or fraud.
* Databricks Free Edition imposed limitations on direct external-storage configuration.
* ML artifacts were therefore handed off manually to the canonical ADLS ML layer.
* A production implementation would use an environment supporting the required external storage integration and deployment controls.
* The existing Azure environment was built incrementally during the portfolio project; Terraform is therefore being introduced as an infrastructure-as-code foundation rather than used to recreate the entire environment on the final project day.

---

# 14. Change Management

Changes to the data contract should be reflected in:

* ingestion scripts
* transformation logic
* validation tests
* downstream Synapse views
* Power BI serving queries
* relevant documentation

Schema or contract changes should be reviewed before being promoted to the main branch.

The repository CI pipeline validates Python compilation and automated tests without requiring access to the live Azure environment.

Live Azure validation is treated as an integration/acceptance activity rather than a prerequisite for every repository test run.
