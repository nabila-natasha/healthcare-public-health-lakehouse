# Day 7 — Power BI Serving, ML Analytics & Anomaly Screening

## Objective

Day 7 completes the business-facing serving and analytics layer of the Azure healthcare/public-health lakehouse.

The objective is to expose validated CDC public-health surveillance data, OpenFDA adverse-event analytics, and OpenFDA machine-learning outputs through Synapse Serverless and Power BI.

The implementation demonstrates:

* Azure Data Factory batch ingestion with REST API pagination
* Event Hubs streaming and CDC Bronze/Silver/Gold processing
* OpenFDA Bronze/Silver/Gold processing
* Synapse Serverless external views over ADLS Gen2 Parquet
* Power BI semantic modelling
* Business-facing analytics dashboards
* XGBoost predictive classification
* Isolation Forest anomaly screening
* Feature-importance interpretation
* ML output serving through the lakehouse
* Data-quality and analytical guardrails

The project uses public or synthetic data only. It does not process PHI or production clinical data.

---

# 1. Day 7 Architecture

```text
                         DATA SOURCES
                              │
             ┌────────────────┴─────────────────┐
             │                                  │
       CDC Archived API                    openFDA API
             │                                  │
             ▼                                  ▼
       Event Hubs                         Azure Data Factory
             │                                  │
             ▼                                  ▼
        ADLS RAW/C DC                     ADLS RAW/openFDA
             │                                  │
             ▼                                  ▼
        Bronze Layer                       Bronze Layer
             │                                  │
             ▼                                  ▼
        Silver Layer                       Silver Layer
             │                                  │
             ▼                                  ▼
          Gold Layer                        Gold Layer
             │                                  │
             └────────────────┬─────────────────┘
                              │
                              ▼
                       Synapse Serverless
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
          Analytics Views              ML Views
                 │                         │
                 └────────────┬────────────┘
                              ▼
                          Power BI
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
       CDC Dashboard     OpenFDA Dashboard    ML & Anomaly
                                               Dashboard
```

---

# 2. Azure Data Factory — OpenFDA Batch Ingestion

## Pipeline

ADF pipeline:

`PL_openFDA_Batch_Ingestion`

Copy activity:

`Copy_openFDA_to_RAW`

Linked services:

* `LS_openFDA_REST`
* `LS_ADLS_healthcare`

Destination:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

The OpenFDA REST API was configured with pagination because the API response limit is smaller than the required extraction volume.

### Final pagination configuration

Relative URL:

```text
@concat(
    'drug/event.json?api_key=',
    dataset().openfda_api_key,
    '&limit=1000&skip={skip}'
)
```

Pagination key:

```text
QueryParameters.{skip}
```

Pagination value:

```text
RANGE:0:3000:1000
```

This produced four API pages:

```text
skip=0
skip=1000
skip=2000
skip=3000
```

Each page returned 1,000 reports.

Validation confirmed:

* JSON documents/pages: 4
* Total reports: 4,000
* Unique `safetyreportid`: 4,000
* Duplicate `safetyreportid`: 0
* First `safetyreportid`: `5801206-7`
* Last `safetyreportid`: `10007321`

`rowsRead = 4` in the ADF Copy activity refers to the four REST response pages, not four adverse-event records.

ADF wrote the paginated responses into one canonical RAW JSON file. Splitting each API page into a separate storage file was not required because API pagination is an ingestion mechanism rather than an ADLS partitioning requirement.

### ADF Copy activity result

```text
dataRead: 79,401,072
dataWritten: 47,543,231
filesWritten: 1
rowsRead: 4
rowsCopied: 4
copyDuration: 40 seconds
errors: []
status: Succeeded
```

The ADF data-consistency verification field reported `NotVerified`; record-level uniqueness was therefore independently validated using the downloaded RAW file.

---

# 3. ADF Scheduled Trigger

A scheduled trigger was configured:

```text
TRG_openFDA_Daily
```

Configuration:

* Frequency: Every 1 day
* Time zone: `(UTC+08:00) Kuala Lumpur, Singapore`
* Start trigger on creation: Enabled

The trigger provides scheduled batch orchestration for OpenFDA ingestion.

This is intentionally separate from the Event Hubs streaming path.

### Architectural distinction

ADF is used for:

```text
Scheduled batch ingestion
```

Event Hubs is used for:

```text
Streaming/event ingestion
```

The CDC path therefore does not depend on the ADF schedule.

---

# 4. OpenFDA Gold Analytics

OpenFDA Gold is stored at:

```text
healthcare/gold/openfda/openfda_gold.parquet
```

Grain:

```text
reporter_country + transmission_date
```

Columns include:

* `reporter_country`
* `transmission_date`
* `adverse_event_reports`
* `serious_reports`
* `death_reports`
* `expedited_reports`
* `serious_report_pct`
* `death_report_pct`
* `expedited_report_pct`

Validation:

* 78 Gold rows
* 34 reporter countries
* 1,000 total reports represented

The Power BI model calculates percentages from additive counts rather than averaging precomputed percentages. This allows percentages to recalculate correctly when users filter by country or date.

Example measures:

```DAX
Total Reports =
SUM(FactOpenFDAAnalytics[adverse_event_reports])

Serious Reports =
SUM(FactOpenFDAAnalytics[serious_reports])

Death Reports =
SUM(FactOpenFDAAnalytics[death_reports])

Expedited Reports =
SUM(FactOpenFDAAnalytics[expedited_reports])

Serious Report % =
DIVIDE([Serious Reports], [Total Reports], 0)

Death Report % =
DIVIDE([Death Reports], [Total Reports], 0)

Expedited Report % =
DIVIDE([Expedited Reports], [Total Reports], 0)
```

---

# 5. Synapse Serverless Serving Layer

Synapse Serverless provides SQL views over ADLS Gen2 Parquet files.

External data source:

```text
HealthcareADLS
```

The following views are used for Power BI serving.

## OpenFDA analytics

```text
dbo.vw_openfda_analytics
```

Source:

```text
gold/openfda/openfda_gold.parquet
```

## OpenFDA ML predictions

```text
dbo.vw_openfda_ml_predictions
```

Source:

```text
ml/openfda/openfda_ml_predictions.parquet
```

## OpenFDA feature importance

```text
dbo.vw_openfda_feature_importance
```

Source:

```text
ml/openfda/openfda_feature_importance.parquet
```

Grain:

```text
one row per model feature
```

Columns:

```text
feature
importance
```

## OpenFDA anomalies

```text
dbo.vw_openfda_anomalies
```

Source:

```text
ml/openfda/openfda_anomalies.parquet
```

Columns:

```text
safetyreportid
anomaly_prediction
anomaly_score
is_anomaly
```

The feature-importance and anomaly outputs are exposed as separate views because they represent different analytical grains.

---

# 6. Databricks ML Outputs

The OpenFDA ML workflow was developed in Databricks Free Edition.

Notebook:

```text
notebooks/Day6_OpenFDA_ML.ipynb
```

The notebook performs:

* Feature preparation
* XGBoost seriousness classification
* Holdout evaluation
* Feature importance extraction
* Isolation Forest anomaly screening

ML artifacts:

```text
healthcare/ml/openfda/openfda_ml_features.parquet
healthcare/ml/openfda/openfda_ml_predictions.parquet
healthcare/ml/openfda/openfda_feature_importance.parquet
healthcare/ml/openfda/openfda_anomalies.parquet
```

The Databricks Free Edition environment uses a managed Unity Catalog volume for ML experimentation.

Because the Free Edition environment does not provide the required arbitrary ADLS Spark configuration for the intended direct external-storage integration, the final ML Parquet outputs were transferred to the canonical ADLS ML layer as a documented manual handoff.

The project therefore does **not** claim a fully automated Databricks-to-ADLS production integration.

---

# 7. XGBoost Model Results

The model was evaluated on a 200-row holdout set.

Recorded results:

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 0.7800 |
| Precision | 0.7831 |
| Recall    | 0.7143 |
| F1        | 0.7471 |
| ROC-AUC   | 0.8759 |
| PR-AUC    | 0.8803 |

Confusion matrix:

```text
True Negative  = 91
False Positive = 18
False Negative = 26
True Positive   = 65
```

The majority-class baseline accuracy was approximately 0.545.

The model results are presented as analytical model performance for this dataset and holdout split. They should not be interpreted as evidence of clinical effectiveness or generalization to the broader adverse-event reporting population.

---

# 8. Feature Importance

Feature importance was extracted directly from the fitted XGBoost model using the fitted preprocessing pipeline.

The exported dataset contains:

```text
feature
importance
```

The Power BI dashboard displays the top model features using a horizontal bar chart.

Examples from the recorded model output include:

```text
categorical__reportercountry_US
numeric__reporting_delay_days
numeric__transmission_year
numeric__transmission_month
numeric__reporterqualification
categorical__reportercountry_DE
```

The dashboard uses human-readable display labels while preserving the original model feature names in the underlying data.

### Interpretation guardrail

Feature importance describes the relative contribution of model features to predictions within this fitted model.

It does not establish:

* causality
* clinical risk
* incidence
* mechanism
* that a country or reporting characteristic causes serious outcomes

The high importance of `reportercountry_US` is treated as a model/data signal requiring further investigation rather than a causal conclusion.

Potential explanations include reporting practices, dataset composition, regulatory processes, or other characteristics of the sampled data.

---

# 9. Isolation Forest Anomaly Screening

Isolation Forest was applied to the ML holdout/test population.

Configuration:

```text
n_estimators = 200
contamination = 0.05
random_state = 42
n_jobs = -1
```

Results:

```text
Records screened: 200
Anomalies detected: 10
```

The 10 anomalies are therefore:

```text
10 / 200 = 5%
```

consistent with the configured contamination level.

The anomaly output contains:

```text
safetyreportid
anomaly_prediction
anomaly_score
is_anomaly
```

The anomaly score is used to order unusual observations for review.

### Interpretation guardrail

Isolation Forest identifies observations with unusual feature patterns relative to the data used by the model.

An anomaly flag does **not** indicate:

* fraud
* data misconduct
* causality
* clinical danger
* adverse-event validity
* patient-level risk

Flagged observations are intended for analytical review.

---

# 10. Power BI Semantic Model

The Power BI model uses separate fact tables with conformed dimensions where appropriate.

## Fact tables

### FactCDCStateSurveillance

Grain:

```text
one row per state and surveillance period
```

### FactOpenFDAAnalytics

Grain:

```text
one row per reporter_country and transmission_date
```

### FactOpenFDAML

Grain:

```text
one row per safetyreportid/model prediction
```

### Feature importance

```text
FACT_OPENFDA_FEATURE_IMPORTANCE
```

Grain:

```text
one row per model feature
```

This is model metadata rather than a transactional fact.

### Anomaly results

```text
FACT_OPENFDA_ANOMALIES
```

Grain:

```text
one row per safetyreportid/anomaly result
```

The feature-importance and anomaly tables are intentionally not joined to the operational fact tables.

---

# 11. Power BI Dashboard 1 — CDC Public Health Surveillance Analytics

## Purpose

Provide historical public-health surveillance analytics using archived CDC data.

This is an analytical dashboard rather than a live clinical monitoring system.

### KPIs

* Total Cases
* Total Deaths
* New Cases
* States Covered

### Visuals

* Cases and deaths over time
* Cases by state
* Deaths by state
* Selected-state trend
* State slicer
* Date-range slicer

### Data interpretation

The CDC dataset is archived historical surveillance data.

The project simulates near-real-time arrival by replaying historical records at an accelerated cadence. It does not represent a genuine real-time CDC feed.

---

# 12. Power BI Dashboard 2 — OpenFDA Surveillance Analytics

## Purpose

Summarize adverse-event reporting volume and reporting patterns.

### KPIs

```text
Total Reports: 1,000
Serious Reports: 454
Serious Report %: 45.4%
Countries: 34
```

### Visuals

* Reports over time
* Reports by reporter country
* Observed seriousness rate by country
* Serious vs non-serious reports
* Date slicer
* Country slicer

### Interpretation guardrail

OpenFDA/FAERS reports are spontaneous adverse-event reports.

They are subject to reporting and selection biases and cannot by themselves establish causality or estimate adverse-event incidence.

Observed reporting proportions should therefore be presented as descriptive surveillance analytics.

---

# 13. Power BI Dashboard 3 — OpenFDA ML & Anomaly Analytics

## Purpose

Provide a business-facing view of the machine-learning outputs.

Dashboard title:

```text
OPENFDA ML & ANOMALY ANALYTICS
```

Subtitle:

```text
Predictive classification and anomaly screening of FDA adverse-event reports
```

## KPI cards

```text
Total Scored       200
Predicted Serious   65
Predicted Serious % 32.5%
Anomalous Reports   10
```

## Predicted seriousness probability

Display the distribution of predicted seriousness probabilities from the ML holdout predictions.

## Confusion matrix

Display:

```text
TN = 91
FP = 18
FN = 26
TP = 65
```

## Holdout Model Performance

Display:

```text
Accuracy   78.00%
Precision  78.31%
Recall     71.43%
F1         74.71%
ROC-AUC    87.59%
PR-AUC     88.03%
```

These metrics are explicitly labelled as holdout-set model performance.

## XGBoost Feature Importance

Display a horizontal bar chart of the top model features.

Dashboard note:

```text
Model-derived importance; not evidence of causality.
```

## Anomaly Screening

Display:

```text
Anomalous Reports = 10
```

alongside an anomaly review table containing:

* Report ID
* Anomaly Score
* Isolation Forest Prediction

The visual is filtered to:

```text
is_anomaly = TRUE
```

and sorted by anomaly score ascending so the most unusual observations appear first.

Dashboard note:

```text
Isolation Forest identifies observations with unusual feature patterns for review. It does not indicate fraud, causality, or clinical risk.
```

---

# 14. Power BI Date Slicers

Date slicers use the dedicated date dimension rather than automatically generated date hierarchies.

Recommended configuration:

```text
DimDate[Date]
```

Slicer type:

```text
Between
```

This provides a calendar-style start/end date selection.

The date column is stored as a true Date data type.

---

# 15. Data Quality Validation

Day 7 validation includes:

## CDC

```text
RAW records:        1,002
Bronze records:     1,000
Quarantine records: 1
```

The remaining difference represents intentionally injected invalid data and duplicate delivery handling.

## OpenFDA

```text
ADF API pages:      4
Reports:            4,000
Unique report IDs:  4,000
Duplicate IDs:      0
```

## OpenFDA Gold

```text
Gold rows:          78
Countries:          34
Total reports:      1,000
```

## ML

```text
Holdout records:    200
Anomalies:          10
```

The ML anomaly count refers only to the 200-row holdout population and must not be interpreted as 10 anomalies across all 1,000 source reports.

---

# 16. Security and Governance

The project avoids committing secrets to GitHub.

Controls include:

* API keys stored outside source-controlled code
* `.env` excluded through `.gitignore`
* Azure identity-based access used where supported
* Synapse external data source configured against ADLS
* Managed identity used for Synapse access
* No patient-identifiable information
* Synthetic/archived public data only
* ML outputs separated from source data
* Analytical limitations documented

The OpenFDA API key is not stored in the repository.

---

# 17. Architectural Decisions

## Why Parquet?

Parquet was selected for Silver, Gold, and ML outputs because it provides:

* typed columns
* columnar storage
* compression
* efficient analytical reads
* compatibility with Synapse and Python/Pandas

## Why calculate percentages in Power BI?

Additive counts are stored in the serving layer while percentage measures are calculated dynamically in DAX.

This prevents incorrect averaging of precomputed percentages when users filter by country or date.

## Why separate ML and anomaly views?

The outputs have different grains:

```text
Predictions
→ one row per report/model prediction

Anomalies
→ one row per report/anomaly result

Feature importance
→ one row per model feature
```

Keeping them separate makes the semantic model clearer.

## Why use a manual Databricks handoff?

The project uses Databricks Free Edition for ML experimentation. The environment does not provide the required arbitrary ADLS Spark configuration for the intended direct external-storage integration.

The project therefore uses a documented manual transfer of final Parquet artifacts into the canonical ADLS ML layer.

This is explicitly documented rather than presented as automated production integration.

---

# 18. Current Status

Day 7 implementation is complete.

Completed:

* [x] OpenFDA REST pagination
* [x] Four-page ingestion validation
* [x] ADF OpenFDA batch pipeline
* [x] ADF daily schedule trigger
* [x] OpenFDA Gold serving
* [x] Synapse OpenFDA analytics view
* [x] Synapse ML prediction view
* [x] Synapse feature-importance view
* [x] Synapse anomaly view
* [x] Power BI OpenFDA analytics model
* [x] Power BI ML prediction model
* [x] Power BI feature-importance table
* [x] Power BI anomaly table
* [x] XGBoost feature-importance visualization
* [x] Isolation Forest anomaly KPI
* [x] Anomaly review table
* [x] ML performance cards
* [x] Dashboard interpretation guardrails
* [x] Day 7 data-quality validation
* [x] Day 7 architectural documentation

---

# 19. Day 7 Completion Criteria

Day 7 is considered complete when:

```text
ADF
  ↓
OpenFDA RAW
  ↓
Bronze → Silver → Gold
  ↓
Synapse Serverless
  ↓
Power BI
```

and

```text
Databricks
  ↓
ML Parquet outputs
  ↓
ADLS ML layer
  ↓
Synapse Serverless
  ↓
Power BI ML & Anomaly Dashboard
```

have been validated end-to-end.

The resulting dashboards provide:

1. Historical public-health surveillance analytics
2. OpenFDA adverse-event reporting analytics
3. ML prediction diagnostics
4. Feature-importance interpretation
5. Anomaly screening for analytical review

The project intentionally avoids presenting model outputs as clinical decisions or causal findings.
