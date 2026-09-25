# Data Model

## 1. Modeling Approach

The project uses separate analytical models for the CDC public-health
surveillance and openFDA adverse-event domains rather than forcing
different source domains into a single relational model.

The two domains have different source structures, business meanings,
and analytical grains.

The data model therefore follows these principles:

* preserve source-domain boundaries
* define analytical grain explicitly
* normalize complex openFDA report structures before analytical aggregation
* avoid artificial relationships between unrelated domains
* expose curated datasets through Synapse Serverless SQL views
* keep ML outputs separate from the core analytical datasets
* use Power BI as the business-facing consumption layer

The overall lakehouse flow is:

```text
Source Data
    │
    ▼
   RAW
    │
    ▼
  BRONZE
    │
    ▼
 SILVER
    │
    ▼
  GOLD
    │
    ├──────────────► Synapse Serverless ► Power BI
    │
    └──────────────► ML Feature Engineering
                              │
                              ▼
                         ML Outputs
                              │
                              ▼
                         Synapse Serverless
                              │
                              ▼
                           Power BI
```

---

## 2. Physical Lakehouse Organization

The physical lakehouse is organized using medallion layers.

```text
healthcare/
│
├── raw/
│   ├── cdc/
│   └── openfda/
│
├── bronze/
│   ├── cdc/
│   └── openfda/
│
├── silver/
│   ├── cdc/
│   └── openfda/
│
├── gold/
│   ├── cdc/
│   └── openfda/
│
└── ml/
    └── openfda/
```

CDC validation also uses a separate quarantine path:

```text
healthcare/quarantine/cdc/
```

Quarantine is an **exception path**, not another medallion layer.

Malformed events are separated during validation rather than being
allowed to continue into the Bronze-to-Gold analytical pipeline.

---

# 3. CDC Public-Health Surveillance Model

## 3.1 Source structure

The CDC source is the archived:

**Weekly United States COVID-19 Cases and Deaths by State**

dataset.

The source records contain fields including:

* `date_updated`
* `state`
* `start_date`
* `end_date`
* `tot_cases`
* `new_cases`
* `tot_deaths`
* `new_deaths`
* `new_historic_cases`
* `new_historic_deaths`

The project wraps source records in a streaming event envelope containing:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

---

## 3.2 Event identity

The CDC event identifier is deterministically generated from:

```text
state | start_date | end_date
```

using SHA-256.

This provides a stable identifier for the same business event across
repeated deliveries.

The identifier is used for:

* duplicate-delivery detection
* Bronze deduplication
* event traceability

It does not replace the source business attributes.

---

## 3.3 CDC Silver grain

The CDC Silver dataset retains one validated analytical event record
per unique `event_id`.

The Silver transformation:

* validates required fields
* preserves event metadata
* retains event time
* retains ingestion time
* deduplicates by `event_id`
* structures the payload into typed columns

---

## 3.4 CDC Gold grain

The CDC Gold dataset represents one public-health surveillance
observation for a source reporting period and geographic unit.

The analytical dataset supports measures such as:

* total cases
* new cases
* total deaths
* new deaths
* historic case counts
* historic death counts
* derived surveillance ratios

The Gold dataset is designed for aggregate public-health surveillance
analysis rather than individual patient analysis.

---

## 3.5 CDC serving model

The CDC Gold dataset is exposed through:

```text
dbo.vw_cdc_surveillance
```

The serving flow is:

```text
CDC Bronze
    │
    ▼
CDC Silver
    │
    ▼
CDC Gold
    │
    ▼
dbo.vw_cdc_surveillance
    │
    ▼
Power BI
```

The corresponding Power BI dashboard is:

```text
US Covid -19 Surveillance Analysis
```

---

# 4. openFDA Adverse-Event Model

## 4.1 Source structure

The openFDA adverse-event source contains nested report structures.

A single adverse-event report can contain:

* patient information
* one or more drugs
* one or more reactions
* reporter information
* transmission metadata
* seriousness indicators

Because these nested structures have different grains, they are
separated during the Silver transformation.

---

## 4.2 openFDA Silver datasets

The project creates three principal Silver datasets.

### Adverse events

```text
adverse_events.parquet
```

Grain:

> One openFDA adverse-event report.

This dataset contains report-level attributes such as:

* `safetyreportid`
* patient attributes
* reporter attributes
* transmission information
* seriousness-related source fields used for analytical processing

---

### Reactions

```text
adverse_event_reactions.parquet
```

Grain:

> One reaction associated with an adverse-event report.

A single report can therefore produce multiple reaction rows.

The report identifier provides traceability back to the parent
adverse-event report.

---

### Drugs

```text
adverse_event_drugs.parquet
```

Grain:

> One drug associated with an adverse-event report.

A single report can therefore produce multiple drug rows.

The report identifier provides traceability back to the parent
adverse-event report.

---

## 4.3 Relationship between openFDA Silver datasets

The logical relationship is:

```text
                 safetyreportid
                       │
                       ▼
             ADVERSE_EVENT_REPORT
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       REACTION_ROWS          DRUG_ROWS
```

The relationship is one-to-many from an adverse-event report to both
reactions and drugs.

This structure prevents repeated reaction and drug information from
being flattened into a single report-level row prematurely.

---

# 5. openFDA Gold Analytical Model

The openFDA Gold dataset aggregates report-level information for
analytical consumption.

```text
openFDA Silver
     │
     ├── adverse_events
     ├── reactions
     └── drugs
             │
             ▼
     Gold Transformation
             │
             ▼
      openfda_gold.parquet
```

The Gold analytical grain is:

> One reporter-country and transmission-date combination.

The principal Gold attributes include:

* `reporter_country`
* `transmission_date`
* `adverse_event_reports`
* `serious_reports`
* `death_reports`
* `expedited_reports`
* `serious_report_pct`
* `death_report_pct`
* `expedited_report_pct`

This model supports aggregate reporting analysis rather than
patient-level clinical analysis.

---

# 6. openFDA ML Feature Model

The ML feature transformation starts from the openFDA Silver report,
reaction, and drug datasets.

```text
adverse_events
      │
      ├───────────────┐
      │               │
      ▼               ▼
 reactions          drugs
      │               │
      └───────┬───────┘
              ▼
      Feature Engineering
              │
              ▼
   openfda_ml_features.parquet
```

The resulting feature dataset contains 1,000 report-level observations.

Important features include:

```text
safetyreportid
patientonsetage
patientonsetageunit
patientsex
reportercountry
reporterqualification
number_of_reactions
number_of_drugs
transmission_year
transmission_month
reporting_delay_days
target_serious
drug_reaction_ratio
```

---

## 6.1 ML target

The classification target is:

```text
target_serious
```

It is derived from the source seriousness indicator.

The source target field is used to create the label and is not retained
as an independent model input.

---

## 6.2 Leakage controls

The following fields are excluded from the model feature matrix because
they can directly encode or strongly reveal the outcome:

```text
seriousnessdeath
fulfillexpeditecriteria
patientdeathdate
companynumb
```

`safetyreportid` is retained for traceability but excluded from model
features.

These controls are documented in:

```text
transformations/ml/openfda_features.py
```

---

# 7. ML Output Model

The ML workflow produces several separate analytical outputs.

```text
                   ML Features
                       │
          ┌────────────┼─────────────┐
          │            │             │
          ▼            ▼             ▼
       XGBoost      SHAP        Isolation Forest
          │            │             │
          ▼            ▼             ▼
     Predictions   Feature       Anomalies
                   Importance
```

The corresponding ADLS ML outputs are:

```text
healthcare/ml/openfda/
├── openfda_ml_features.parquet
├── openfda_ml_predictions.parquet
├── openfda_feature_importance.parquet
└── openfda_anomalies.parquet
```

These outputs are treated as analytical ML artifacts rather than
clinical decision outputs.

---

## 7.1 ML predictions

The prediction dataset contains the model's classification outputs
associated with the evaluated adverse-event reports.

Serving view:

```text
dbo.vw_openfda_ml_predictions
```

---

## 7.2 Feature importance

The feature-importance dataset contains the XGBoost feature-importance
results used for model interpretation.

Serving view:

```text
dbo.vw_openfda_feature_importance
```

The feature-importance results describe model behavior on this dataset;
they do not establish causal relationships.

---

## 7.3 Anomalies

The anomaly dataset contains Isolation Forest outputs.

Serving view:

```text
dbo.vw_openfda_anomalies
```

The anomaly flag identifies observations with unusual feature patterns
for analytical review.

It does not indicate:

* fraud
* causality
* clinical risk
* adverse-event validity

---

# 8. Synapse Serverless Serving Model

Azure Synapse Serverless SQL provides a stable analytical interface
between the curated lakehouse data and Power BI.

The project contains five serving views.

```text
                         Synapse Serverless
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
        ▼                       ▼                        ▼
vw_cdc_surveillance    vw_openfda_analytics    ML serving views
                                                     │
                                      ┌──────────────┼──────────────┐
                                      │              │              │
                                      ▼              ▼              ▼
                              ML predictions   Feature importance  Anomalies
```

The complete serving layer is:

```text
dbo.vw_cdc_surveillance
dbo.vw_openfda_analytics
dbo.vw_openfda_ml_predictions
dbo.vw_openfda_feature_importance
dbo.vw_openfda_anomalies
```

---

## 8.1 Serving view responsibilities

| View                                | Analytical purpose                 |
| ----------------------------------- | ---------------------------------- |
| `dbo.vw_cdc_surveillance`           | CDC public-health surveillance     |
| `dbo.vw_openfda_analytics`          | openFDA adverse-event analytics    |
| `dbo.vw_openfda_ml_predictions`     | ML seriousness predictions         |
| `dbo.vw_openfda_feature_importance` | XGBoost feature-importance results |
| `dbo.vw_openfda_anomalies`          | Isolation Forest anomaly results   |

These views form the primary SQL serving interface consumed by Power BI.

---

# 9. Power BI Analytical Model

Power BI consumes the Synapse serving views rather than directly
depending on the raw ingestion structures.

The analytical consumption model contains separate domain and ML
outputs.

```text
                    Synapse Serverless
                           │
          ┌────────────────┼───────────────────┐
          │                │                   │
          ▼                ▼                   ▼
       CDC View       openFDA View         ML Views
          │                │                   │
          ▼                ▼          ┌────────┼─────────┐
        CDC BI          openFDA BI    │        │         │
                                     Pred.   Feature   Anomaly
                                      │       Imp.       │
                                      └────────┬─────────┘
                                               ▼
                                         ML Analytics
```

The project contains three Power BI dashboards:

```text
US Covid -19 Surveillance Analysis

US OPENFDA Adverse Event Analysis

US OPENFDA ML Risk & Anomaly Analytics
```

The ML outputs are intentionally presented as analytical and
diagnostic information rather than clinical decision support.

---

# 10. Data Model vs. Lakehouse Architecture

The project distinguishes between the physical lakehouse architecture
and the analytical data model.

### Lakehouse architecture

Describes:

* ingestion
* storage
* medallion layers
* streaming
* batch processing
* ML processing
* SQL serving

Example:

```text
RAW
 │
 ▼
BRONZE
 │
 ▼
SILVER
 │
 ▼
GOLD
 │
 ├──► Synapse
 │
 └──► ML
```

### Analytical data model

Describes:

* dataset grains
* report/reaction/drug relationships
* analytical aggregates
* ML output structures
* serving views
* Power BI consumption

This distinction prevents the ADLS folder structure from being
mistaken for a relational or semantic data model.

---

# 11. Modeling Decisions

## Separate CDC and openFDA domains

The two domains represent different analytical processes and therefore
are not forced into a common fact table.

There is no meaningful event-level relationship between an individual
CDC surveillance observation and an individual openFDA adverse-event
report.

They are therefore served as separate analytical domains.

---

## Preserve nested openFDA grains

Drugs and reactions are kept at their natural one-to-many grains in
Silver rather than being unnecessarily flattened into the report-level
dataset.

This preserves source detail while allowing controlled analytical
aggregation.

---

## Aggregate openFDA Gold data

The Gold dataset intentionally moves from the report-level source
structure to a reporting-country and transmission-date analytical
grain.

This produces a smaller dataset suitable for aggregate analytics and
Power BI.

---

## Separate ML outputs from core analytical data

Predictions, feature importance, and anomaly results are stored as
separate ML outputs rather than modifying the underlying openFDA
analytical Gold dataset.

This keeps model outputs traceable and allows the analytical dataset
to remain independent of a particular model implementation.

---

# 12. Current Model Boundaries

The current implementation intentionally does not claim:

* a universal enterprise-wide dimensional model
* a single star schema across both domains
* a direct relational relationship between CDC and openFDA observations
* patient-level clinical analytics
* clinical decision support
* causal relationships from adverse-event data

The model is designed for the specific analytical and ML workloads
implemented in this portfolio project.

---

# 13. Related Documentation

Related architecture and implementation documentation:

* [`docs/architecture.md`](architecture.md)
* [`docs/architecture-decisions.md`](architecture-decisions.md)
* [`docs/data-contract.md`](data-contract.md)
* [`docs/databricks-integration.md`](databricks-integration.md)
* [`docs/day4-cdc-streaming.md`](day4-cdc-streaming.md)
* [`docs/day7-power-bi-serving.md`](day7-power-bi-serving.md)
* [`docs/security-governance.md`](security-governance.md)
* [`docs/project-completion.md`](project-completion.md)
