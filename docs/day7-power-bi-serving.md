# Day 7 — Power BI Serving, Batch Validation & Analytics

## 1. Day 7 Objective

Day 7 focuses on completing the analytical serving layer and preparing the Azure lakehouse outputs for business-facing analytics in Power BI.

The main objectives are:

1. Validate the OpenFDA paginated batch ingestion implemented with Azure Data Factory.
2. Configure scheduled execution for the OpenFDA batch pipeline.
3. Expose curated CDC, OpenFDA, and OpenFDA ML datasets through Synapse Serverless.
4. Establish a Power BI semantic model using fact and dimension tables.
5. Build three business-facing dashboards covering:

   * Public-health surveillance analytics
   * OpenFDA adverse-event analytics
   * OpenFDA ML and anomaly analytics
6. Validate that dashboard metrics reconcile with the underlying lakehouse data.
7. Document architectural and analytical decisions for portfolio and interview use.

---

# 2. Day 7 Architecture

The Day 7 analytical flow is:

```text
                    ┌──────────────────────┐
                    │   CDC Historical     │
                    │ Surveillance Dataset │
                    └──────────┬───────────┘
                               │
                               ▼
                         Event Producer
                               │
                               ▼
                      Azure Event Hubs
                               │
                               ▼
                         Bronze / CDC
                               │
                               ▼
                         Silver / CDC
                               │
                               ▼
                          Gold / CDC
                               │
                               ▼
                       Synapse Serverless
                               │
                               ▼
                            Power BI


┌───────────────────┐
│     openFDA API   │
└─────────┬─────────┘
          │
          ▼
 Azure Data Factory
          │
          ▼
     ADLS RAW
          │
          ▼
    ADLS Bronze
          │
          ▼
    ADLS Silver
          │
          ▼
     ADLS Gold
          │
          ├───────────────────────┐
          │                       │
          ▼                       ▼
 Synapse Serverless       Databricks Free Edition
          │                       │
          │                       ▼
          │                 ML Predictions
          │                       │
          │                       ▼
          │                  ADLS ML layer
          │                       │
          └───────────┬───────────┘
                      ▼
                   Power BI
```

Power BI is therefore positioned as the business-facing consumption layer rather than as the transformation engine.

---

# 3. OpenFDA Batch Ingestion Validation

## 3.1 Azure Data Factory Pipeline

The OpenFDA batch ingestion pipeline is:

```text
PL_openFDA_Batch_Ingestion
```

The pipeline uses:

* Azure Data Factory
* REST linked service
* REST dataset
* ADLS Gen2 sink
* Dataset parameter for the OpenFDA API key
* REST pagination

The pipeline writes the canonical raw OpenFDA dataset to:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

---

## 3.2 Pagination Design

The OpenFDA API uses `skip` and `limit` parameters for pagination.

The final ADF relative URL is:

```text
@concat(
    'drug/event.json?api_key=',
    dataset().openfda_api_key,
    '&limit=1000&skip={skip}'
)
```

The pagination configuration is:

```text
Pagination Key:
QueryParameters.{skip}

Pagination Value:
RANGE:0:3000:1000
```

This results in four API requests:

```text
skip=0
skip=1000
skip=2000
skip=3000
```

Each request retrieves up to 1,000 reports.

---

## 3.3 Pagination Validation

The API pagination was independently validated before relying on the ADF configuration.

| Page |  Skip | Results | First safetyreportid | Last safetyreportid |
| ---- | ----: | ------: | -------------------- | ------------------- |
| 1    |     0 |   1,000 | 5801206-7            | 10004305            |
| 2    | 1,000 |   1,000 | 10004306             | 10005311            |
| 3    | 2,000 |   1,000 | 10005312             | 10006318            |
| 4    | 3,000 |   1,000 | 10006319             | 10007321            |

The final four-page ADF validation produced:

```text
JSON documents:       4
Total reports:        4,000
Unique safetyreportid: 4,000
Duplicate IDs:        0
First safetyreportid: 5801206-7
Last safetyreportid:  10007321
```

This demonstrates that the pagination configuration retrieves four distinct pages rather than repeatedly retrieving the first page.

---

## 3.4 ADF Copy Activity Result

The successful ADF Copy activity returned:

```text
dataRead:              79,401,072
dataWritten:           47,543,231
filesWritten:          1
rowsRead:              4
rowsCopied:            4
copyDuration:          40 seconds
throughput:            3781.003
errors:                []
parallelCopies:        1
```

An important interpretation is that:

```text
rowsRead = 4
```

does **not** mean four OpenFDA reports were ingested.

It represents four paginated REST response documents.

The four response pages were combined into the canonical raw JSON output:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

This is intentional. API pagination controls how data is retrieved; it does not require the raw dataset to be physically partitioned into four files.

---

# 4. OpenFDA Analytical Data Layers

The canonical OpenFDA data flow is:

```text
RAW
healthcare/raw/openfda/openfda_adverse_events.json
        │
        ▼
BRONZE
healthcare/bronze/openfda/openfda_adverse_events.csv
        │
        ▼
SILVER
healthcare/silver/openfda/
├── adverse_events.parquet
├── adverse_event_reactions.parquet
└── adverse_event_drugs.parquet
        │
        ▼
GOLD
healthcare/gold/openfda/openfda_gold.parquet
        │
        ├─────────────────────┐
        ▼                     ▼
Synapse Serverless       ML Feature Engineering
                              │
                              ▼
                         Databricks ML
                              │
                              ▼
                           ML Layer
```

---

# 5. OpenFDA Gold Analytical Dataset

The OpenFDA Gold dataset is:

```text
healthcare/gold/openfda/openfda_gold.parquet
```

Its analytical grain is:

```text
reporter_country + transmission_date
```

The validated dataset contains:

```text
Rows:             78
Countries:        34
Source reports:   1,000
```

The additive report count reconciles to:

```text
SUM(adverse_event_reports) = 1,000
```

The Gold dataset contains:

```text
reporter_country
transmission_date
adverse_event_reports
serious_reports
death_reports
expedited_reports
serious_report_pct
death_report_pct
expedited_report_pct
```

The percentage fields are retained in the Gold dataset for analytical completeness.

However, Power BI percentage measures are calculated from additive counts rather than by averaging these precomputed percentages.

For example:

```DAX
Serious Report % =
DIVIDE(
    [Serious Reports],
    [Total Reports],
    0
)
```

This ensures that the percentage responds correctly when users filter by country, date, or other dimensions.

---

# 6. Synapse Serverless Analytical Serving

Synapse Serverless is used as the SQL-based serving layer over ADLS Parquet files.

The external data source is:

```text
HealthcareADLS
```

The OpenFDA analytical view is:

```text
dbo.vw_openfda_analytics
```

The view exposes:

```text
reporter_country
transmission_date
adverse_event_reports
serious_reports
death_reports
expedited_reports
```

The view reads:

```text
gold/openfda/openfda_gold.parquet
```

using:

```sql
OPENROWSET(
    BULK 'gold/openfda/openfda_gold.parquet',
    DATA_SOURCE = 'HealthcareADLS',
    FORMAT = 'PARQUET'
)
```

The date is converted to a SQL `date` type before being exposed to Power BI.

---

# 7. ML Serving Layer

The Databricks Free Edition ML experiment produces:

```text
openfda_ml_predictions.parquet
```

The canonical ADLS ML location is:

```text
healthcare/ml/openfda/openfda_ml_predictions.parquet
```

The Synapse serving view is:

```text
dbo.vw_openfda_ml_predictions
```

This view provides the prediction output for Power BI.

The ML layer is intended for:

* predictive screening of reported-event seriousness
* unusual reporting-pattern screening
* model performance analysis
* feature-importance analysis

It is **not** intended to provide:

* clinical diagnosis
* clinical decision support
* causal inference
* population incidence estimates
* fraud determinations

An anomaly is treated as an unusual reporting pattern requiring further review, rather than automatically representing fraud, danger, or a clinical issue.

---

# 8. Power BI Semantic Model

Power BI uses a dimensional model rather than directly connecting every visual to raw datasets.

The planned model contains three independent fact tables:

```text
FactCDCStateSurveillance
FactOpenFDAAnalytics
FactOpenFDAML
```

and shared dimensions where appropriate:

```text
DimDate
DimCountry
DimState
```

The conceptual model is:

```text
                 DimDate
                    │
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
FactCDCState          FactOpenFDAAnalytics
Surveillance                  │
                              │
                              ▼
                         DimCountry


                         DimCountry
                              │
                              ▼
                        FactOpenFDAML
```

The facts remain independent.

There are no direct fact-to-fact relationships.

This prevents accidental filter propagation between unrelated analytical grains.

---

# 9. Fact Table Grains

## 9.1 CDC Fact

```text
FactCDCStateSurveillance
```

Grain:

```text
one row per state and surveillance period
```

Primary analytical fields include:

```text
state
date
tot_cases
new_cases
tot_deaths
new_deaths
```

---

## 9.2 OpenFDA Analytics Fact

```text
FactOpenFDAAnalytics
```

Grain:

```text
one row per reporter country and transmission date
```

This table supports reporting-volume and seriousness analysis.

---

## 9.3 OpenFDA ML Fact

```text
FactOpenFDAML
```

Grain:

```text
one row per safetyreportid and model prediction
```

This table supports:

* predicted seriousness
* prediction probability
* actual versus predicted classification
* anomaly screening
* model diagnostics

---

# 10. Date Dimension

A conformed `DimDate` is used for date filtering.

The dimension contains:

```text
DateKey
Date
Year
Quarter
Month
MonthNumber
MonthName
YearMonth
```

The Power BI model uses:

```text
DimDate[Date]
```

for calendar-based filtering.

The date column is used instead of an automatically generated Power BI date hierarchy so that the model has explicit control over date attributes.

---

# 11. Power BI Dashboard Design

Three dashboards are being developed.

## Dashboard 1 — CDC Public Health Surveillance Analytics

### Purpose

Provide historical public-health surveillance analytics from the archived CDC dataset.

This dashboard is intended for analytical and reporting purposes rather than live clinical monitoring.

### KPIs

```text
Total Cases
Total Deaths
New Cases
States Covered
```

### Planned visuals

* Cases over time
* Deaths over time
* Cases by state
* Deaths by state
* Selected-state trend
* Date slicer
* State slicer

### Questions addressed

* How did reported cases change over the surveillance period?
* How did reported deaths change?
* Which states account for the largest reported volumes?
* How do patterns differ when the user selects a specific state or period?

---

# 12. OpenFDA Surveillance Analytics

### Purpose

Provide descriptive analytics of adverse-event reporting patterns.

### KPIs

```text
Total Reports
Serious Reports
Serious Report %
Countries Covered
```

### Planned visuals

* Reports over time
* Reports by country
* Observed seriousness rate by country
* Serious versus non-serious reports
* Date slicer
* Country slicer

### Questions addressed

* How are reports distributed over time?
* How are reports distributed geographically?
* What proportion of reports are classified as serious?
* How do report volume and observed seriousness rate differ across countries?

### Interpretation

The dashboard describes reported-event patterns.

It does not estimate population incidence or establish causality.

Differences between countries may reflect factors such as:

* reporting practices
* dataset composition
* regulatory processes
* reporting volume
* other characteristics of the reporting system

Therefore, a higher observed reporting proportion should not automatically be interpreted as a higher underlying population risk.

---

# 13. OpenFDA ML & Anomaly Analytics

### Purpose

Present the output of the ML experimentation layer in a business-readable format.

### KPIs

```text
Total Scored Reports
Predicted Serious
Predicted Serious %
Anomalies
```

### Planned visuals

* Predicted probability distribution
* Confusion matrix
* Model performance metrics
* Feature importance
* Anomaly review table

### Recorded model performance

The XGBoost model was evaluated on a 200-row holdout set.

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

The model results are included as analytical evidence rather than as evidence of clinical performance.

---

# 14. ML Interpretation Guardrails

The model uses reported adverse-event data to predict the dataset's seriousness classification.

The model should therefore be interpreted as a predictive analytics experiment.

It should not be described as:

```text
predicting patient outcomes
diagnosing patients
predicting causal risk
estimating adverse-event incidence
```

Feature importance should also be interpreted cautiously.

For example, a high importance for reporter country is a model/data signal. It does not demonstrate that geography causes seriousness.

Potential explanations include differences in:

* reporting behaviour
* regulatory processes
* dataset composition
* reporting systems
* sample distribution

Further validation using a larger and more representative dataset would be required before making stronger conclusions.

---

# 15. Data Quality Validation

Day 7 validation includes reconciliation between ingestion, transformation, serving, and reporting layers.

Key checks include:

| Check                                | Expected |
| ------------------------------------ | -------: |
| OpenFDA source reports               |    1,000 |
| OpenFDA Gold rows                    |       78 |
| OpenFDA countries                    |       34 |
| Gold report-count sum                |    1,000 |
| Serious reports                      |      454 |
| OpenFDA API pagination pages         |        4 |
| Unique IDs across pagination test    |    4,000 |
| Duplicate IDs across pagination test |        0 |

The purpose of these checks is to ensure that aggregation has not changed the underlying report population unexpectedly.

---

# 16. Scheduled Batch Ingestion

A scheduled Azure Data Factory trigger has been configured:

```text
TRG_openFDA_Daily
```

Configuration:

```text
Trigger type: Schedule
Frequency:     Every 1 day
Time zone:     (UTC+08:00) Kuala Lumpur, Singapore
```

The trigger separates orchestration logic from execution timing.

The pipeline defines:

```text
what should happen
```

while the trigger defines:

```text
when the pipeline should run
```

The current raw sink uses the canonical OpenFDA path:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

A future production hardening step could introduce run/date-partitioned raw paths to improve historical retention and rerun traceability.

For this portfolio implementation, the fixed canonical path is retained to keep the architecture simple and reproducible.

---

# 17. Security and Credential Handling

The OpenFDA API key is supplied to Azure Data Factory through a dataset parameter.

The API key is not stored in the GitHub repository.

Repository documentation and source code must not contain:

* API keys
* connection strings
* storage account keys
* passwords
* SAS tokens
* access tokens

The repository uses placeholders where configuration examples are required.

Example:

```text
EVENT_HUB_CONNECTION_STRING=
```

rather than storing an actual credential.

---

# 18. Architectural Decisions

## 18.1 Why Parquet?

Parquet is used for Silver, Gold, and ML outputs because it provides:

* columnar storage
* typed columns
* compression
* efficient analytical reads
* compatibility with Synapse Serverless
* compatibility with Python/Pandas/PyArrow
* efficient downstream Power BI serving

---

## 18.2 Why Synapse Serverless?

Synapse Serverless provides a SQL-based analytical access layer over ADLS without requiring a dedicated SQL pool.

This is appropriate for the portfolio project because the workload is primarily analytical and does not require an always-running dedicated warehouse.

---

## 18.3 Why Calculate Percentages in Power BI?

The Gold layer contains additive counts.

Power BI calculates ratios from those counts:

```text
Serious Reports / Total Reports
```

rather than averaging precomputed percentages.

This ensures that filtering by country, date, or other dimensions produces a context-appropriate percentage.

---

## 18.4 Why Keep CDC and OpenFDA Facts Separate?

The datasets have different business meanings and different grains.

CDC:

```text
state + surveillance period
```

OpenFDA:

```text
reporter country + transmission date
```

OpenFDA ML:

```text
safety report + prediction
```

Combining these into one fact table would create an artificial grain and could produce misleading aggregations.

The semantic model therefore uses independent fact tables with shared dimensions only where a valid relationship exists.

---

# 19. Day 7 Status

### Completed

* [x] OpenFDA REST pagination implemented
* [x] Four-page pagination independently validated
* [x] 4,000 unique pagination-test reports validated
* [x] Zero duplicate IDs in pagination test
* [x] ADF four-page copy successfully executed
* [x] Canonical OpenFDA RAW path established
* [x] OpenFDA Gold dataset validated
* [x] Synapse OpenFDA analytical view created
* [x] Synapse OpenFDA ML serving view available
* [x] Daily ADF trigger configured
* [x] Power BI analytical model designed
* [x] CDC dashboard design defined
* [x] OpenFDA dashboard design defined
* [x] OpenFDA ML dashboard design defined

### In Progress

* [ ] Complete Power BI CDC dashboard
* [ ] Complete Power BI OpenFDA dashboard
* [ ] Complete Power BI ML/anomaly dashboard
* [ ] Validate dashboard KPI totals against Synapse
* [ ] Capture final dashboard screenshots
* [ ] Finalize Day 7 documentation after dashboard validation

---

# 20. Day 7 Completion Criteria

Day 7 will be considered complete when:

1. The three Power BI dashboards are implemented.
2. Date and categorical slicers correctly filter the relevant fact tables.
3. Dashboard KPI totals reconcile with Synapse/source validation.
4. No accidental fact-to-fact relationships exist.
5. Percentage measures are calculated from additive counts.
6. ML metrics shown in Power BI match the recorded model results.
7. Anomaly results are presented as review candidates rather than definitive conclusions.
8. Dashboard screenshots are captured for the repository.
9. Day 7 documentation is updated with final validation results.

---

# 21. Portfolio Engineering Takeaway

Day 7 demonstrates the transition from data engineering pipelines into an analytical serving layer.

The project now connects:

```text
Data Sources
    ↓
Ingestion
    ↓
ADLS Gen2
    ↓
Bronze / Silver / Gold
    ↓
Synapse Serverless
    ↓
Power BI Semantic Model
    ↓
Business-facing Analytics
```

The ML branch extends this architecture:

```text
OpenFDA Silver
    ↓
Feature Engineering
    ↓
Databricks ML
    ↓
Prediction / Anomaly Outputs
    ↓
ADLS ML Layer
    ↓
Synapse Serverless
    ↓
Power BI
```

The key engineering principle is to keep ingestion, transformation, analytical serving, machine learning, and visualization as separate layers with explicit data contracts and validation points.
