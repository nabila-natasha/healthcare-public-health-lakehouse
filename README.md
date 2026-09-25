# Healthcare Public Health Surveillance & Risk Analytics Lakehouse

An end-to-end Azure data engineering and analytics portfolio project demonstrating batch ingestion, simulated streaming ingestion, medallion lakehouse architecture, SQL serving, Power BI analytics, machine learning, data quality, governance, CI/CD, and infrastructure-as-code.

> **Portfolio scope:** This project uses public and synthetic data only. It is an engineering and analytics demonstration, not a clinical system, patient-monitoring platform, or production healthcare application.

---

## 1. Project Overview

Healthcare and public-health data often arrives through different operational patterns.

This project demonstrates how those patterns can be integrated into a single analytical platform:

* **CDC archived public-health data** is replayed at an accelerated cadence to simulate near-real-time event arrival.
* **openFDA adverse-event data** is ingested through scheduled batch processing.
* **Azure Data Lake Storage Gen2** provides the common lakehouse storage boundary.
* **Python/Pandas** performs transformation and validation logic.
* **Synapse Serverless SQL** provides a query-serving layer.
* **Power BI Desktop** provides business-facing analytics.
* **Databricks Free Edition** is used for machine-learning experimentation and model diagnostics.
* **GitHub Actions** validates application and data-engineering code.
* **Terraform** provides the foundation for future infrastructure-as-code management.

The project deliberately documents platform limitations and implementation boundaries instead of representing incomplete capabilities as production functionality.

---

## 2. Business and Engineering Objectives

The project was designed to answer practical data-engineering questions such as:

1. How can batch and streaming ingestion patterns coexist in one lakehouse?
2. How can historical public-health data be replayed reproducibly without claiming to be a live production feed?
3. How should raw, validated, transformed, analytical, and ML data be separated?
4. How can duplicate deliveries and malformed streaming events be detected?
5. How can public-health and pharmaceutical safety data be transformed into analytical datasets?
6. How can machine-learning outputs be incorporated into an analytical serving layer?
7. How should ML leakage be controlled?
8. How can explainability and anomaly detection be presented without making causal or clinical claims?
9. How should security, governance, CI/CD, and infrastructure-as-code be incorporated into a portfolio-grade platform?
10. How should architectural limitations be documented and communicated?

---

## 3. Architecture

```text
                         PUBLIC / SYNTHETIC DATA
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
          CDC Archived Data                    openFDA API
                 │                                 │
        Historical Replay                     Azure Data Factory
                 │                                 │
                 ▼                                 ▼
          Azure Event Hubs                 ADLS Gen2 RAW
                 │                                 │
                 ▼                                 ▼
          Python Consumer                 ADLS Gen2 BRONZE
                 │                                 │
                 ▼                                 │
          ADLS Gen2 BRONZE                        │
                 │                                 │
                 └──────────────┬──────────────────┘
                                │
                                ▼
                       Python Transformations
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
             SILVER                         GOLD
                 │                             │
                 └──────────────┬──────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
             Synapse Serverless       Databricks ML
                    │                       │
                    │              ML predictions /
                    │              feature importance /
                    │              anomaly detection
                    │                       │
                    │              Controlled manual
                    │                  handoff
                    │                       │
                    │                       ▼
                    │                 ADLS ML layer
                    │                       │
                    └───────────────┬───────┘
                                    │
                                    ▼
                              Power BI Desktop
```

See [`docs/architecture.md`](docs/architecture.md) for the detailed architecture and implementation status.

---

## 4. Technology Stack

| Area                   | Technology                   |
| ---------------------- | ---------------------------- |
| Cloud platform         | Microsoft Azure              |
| Object/lake storage    | Azure Data Lake Storage Gen2 |
| Streaming              | Azure Event Hubs             |
| Batch orchestration    | Azure Data Factory           |
| SQL serving            | Azure Synapse Serverless SQL |
| ML experimentation     | Databricks Free Edition      |
| Transformation         | Python / Pandas / PyArrow    |
| Machine learning       | XGBoost / Isolation Forest   |
| Explainability         | SHAP                         |
| Experiment tracking    | MLflow                       |
| BI                     | Power BI Desktop             |
| CI/CD                  | GitHub Actions               |
| Infrastructure as code | Terraform                    |
| Testing                | pytest                       |
| Analytical format      | Parquet                      |
| Source control         | Git / GitHub                 |

---

## 5. Data Sources

### CDC public-health surveillance data

The project uses the archived CDC dataset:

**Weekly United States COVID-19 Cases and Deaths by State - ARCHIVED**

Dataset ID:

```text
pwn4-m3yp
```

The source is historical and discontinued. It is therefore replayed at an accelerated cadence to simulate near-real-time event arrival.

The project preserves:

* `event_time`
* `ingestion_time`
* source metadata
* deterministic event identity
* payload data

Synthetic faults are injected to demonstrate streaming data-quality handling.

This is **not a live CDC feed**.

### openFDA adverse-event data

openFDA adverse-event data is ingested through the FDA REST API using Azure Data Factory.

The batch pipeline uses API pagination and stores the retrieved data in the ADLS RAW layer before downstream transformation.

The project treats adverse-event reports as observational safety-reporting data. The ML analysis does not establish causality or estimate population incidence.

---

## 6. Lakehouse Data Layers

The project follows a medallion-style structure.

```text
RAW
 │
 │ source-preserving ingestion
 ▼
BRONZE
 │
 │ validation / normalization
 ▼
SILVER
 │
 │ analytical transformations
 ▼
GOLD
 │
 ├──────────────► Synapse Serverless ► Power BI
 │
 └──────────────► ML feature engineering
                         │
                         ▼
                    ML outputs
```

### RAW

Preserves source-oriented ingestion.

Examples:

```text
healthcare/raw/openfda/openfda_adverse_events.json
healthcare/raw/cdc/...
```

### BRONZE

Contains validated ingestion outputs.

CDC streaming validation separates malformed events into a quarantine area.

### SILVER

Contains structured, typed Parquet datasets.

Examples:

```text
adverse_events.parquet
adverse_event_reactions.parquet
adverse_event_drugs.parquet
```

### GOLD

Contains business/analytical datasets.

For example, the openFDA Gold dataset aggregates reports by:

```text
reporter_country
transmission_date
```

### ML

Contains machine-learning features and model outputs.

```text
healthcare/ml/openfda/
├── openfda_ml_features.parquet
├── openfda_ml_predictions.parquet
├── openfda_feature_importance.parquet
└── openfda_anomalies.parquet
```

---

## 7. Streaming Data Engineering

The CDC pipeline demonstrates a streaming ingestion pattern using Azure Event Hubs and a Python consumer.

The source data is historical. It is replayed at an accelerated cadence to simulate near-real-time event arrival.

The pipeline preserves both:

```text
event_time
ingestion_time
```

This allows the project to distinguish the business/event timestamp from the time the platform received the message.

### Event identity

The CDC producer generates a deterministic event ID from:

```text
state|start_date|end_date
```

using SHA-256.

This allows the same business event to produce the same identifier if it is delivered more than once.

The identifier is used for duplicate detection and traceability. It is not a reversible representation of the underlying payload.

### Fault injection

The streaming demonstration intentionally includes:

* valid events
* a delayed valid event
* a duplicate delivery
* a malformed event missing `event_time`

Final validation results:

| Layer      | Records |
| ---------- | ------: |
| RAW        |   1,002 |
| BRONZE     |   1,000 |
| Quarantine |       1 |

The malformed event was quarantined rather than silently discarded.

---

## 8. Batch Data Engineering

Azure Data Factory is used for openFDA batch ingestion.

The implemented pipeline:

```text
openFDA REST API
      │
      ▼
Azure Data Factory
      │
      ▼
ADLS Gen2 RAW
```

The final pagination test retrieved:

* 4 API pages
* 4,000 reports
* 4,000 unique `safetyreportid` values
* 0 duplicate report IDs

The ADF copy operation wrote the four API responses into one combined RAW JSON file.

The ADF output reported:

```text
rowsRead = 4
```

This represents the four REST response pages, not four adverse-event reports.

The scheduled trigger is configured for daily execution.

---

## 9. Transformation Pipeline

Python transformation modules implement the Silver and Gold processing stages.

```text
transformations/
├── silver/
│   ├── cdc_bronze_to_silver.py
│   └── openfda_bronze_to_silver.py
├── gold/
│   ├── cdc_silver_to_gold.py
│   └── openfda_silver_to_gold.py
└── ml/
    └── openfda_features.py
```

Parquet is used for analytical datasets because it provides:

* typed columns
* columnar storage
* efficient analytical reads
* compression
* interoperability with analytical tools

---

## 10. Data Quality

The project includes automated validation using pytest.

Validation covers:

* required streaming fields
* null required fields
* deterministic event IDs
* duplicate event detection
* changed business keys producing different IDs
* CDC Silver-to-Gold reconciliation
* CDC Gold grain
* openFDA `safetyreportid` uniqueness
* duplicate report detection
* ML target validity
* ML leakage exclusions

The test suite is executed automatically by GitHub Actions.

---

## 11. Machine Learning

The ML component focuses on **adverse-event seriousness classification and anomaly screening**.

### Feature engineering

The ML feature pipeline derives features including:

* number of reactions
* number of drugs
* transmission year
* transmission month
* reporting delay
* drug/reaction ratio
* reporter country
* reporter qualification
* patient age
* patient sex

The target is a normalized binary seriousness indicator.

Potential leakage fields such as:

```text
seriousnessdeath
fulfillexpeditecriteria
patientdeathdate
companynumb
```

are explicitly excluded from the model feature set.

### XGBoost classification

The recorded holdout results are:

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 0.7800 |
| Precision | 0.7831 |
| Recall    | 0.7143 |
| F1        | 0.7471 |
| ROC-AUC   | 0.8759 |
| PR-AUC    | 0.8803 |

The holdout contains 200 observations.

Confusion matrix:

```text
True Negative  = 91
False Positive = 18
False Negative = 26
True Positive   = 65
```

These results are reported as experimental model results on the project dataset. They should not be interpreted as clinical performance or population-level predictive performance.

### Feature importance

Feature importance is exported as a separate ML dataset and exposed through Synapse for analytical inspection.

High feature importance for a variable does not demonstrate causality.

For example, country-related importance may reflect reporting practices, dataset composition, regulatory processes, or other characteristics of the sample.

A larger and more representative dataset would be required for stronger conclusions.

### Isolation Forest

Isolation Forest is used to identify observations with unusual feature patterns.

Configuration:

```text
n_estimators = 200
contamination = 0.05
random_state = 42
```

On the 200-row holdout:

```text
Rows evaluated = 200
Anomalies detected = 10
```

The anomaly output is intended for analytical review.

It does not indicate fraud, causality, or clinical risk.

### Explainability

SHAP is used to support model diagnostics and interpretation.

MLflow is used within the Databricks experimentation workflow for experiment tracking.

---

## 12. Databricks Integration Boundary

Databricks Free Edition is used as an ML experimentation environment.

The project uses a managed Unity Catalog volume:

```text
/Volumes/workspace/default/openfda_ml/
```

The Free Edition environment imposes integration limitations around direct access to the project's ADLS Gen2 account through arbitrary Spark filesystem configuration.

Therefore, the current workflow uses a controlled handoff:

```text
ADLS ML features
       │
       ▼
Databricks Free Edition
       │
       ├── XGBoost
       ├── SHAP
       ├── Isolation Forest
       └── MLflow
       │
       ▼
ML Parquet outputs
       │
       ▼
Controlled handoff to ADLS ML layer
       │
       ▼
Synapse Serverless
       │
       ▼
Power BI
```

This is a documented portfolio constraint rather than a claim of fully automated Databricks-to-ADLS orchestration.

See [`docs/databricks-integration.md`](docs/databricks-integration.md) and [`docs/adr/ADR-005-databricks-free-edition-integration.md`](docs/adr/ADR-005-databricks-free-edition-integration.md).

---

## 13. SQL Serving

Azure Synapse Serverless SQL provides the analytical serving layer.

The project exposes views including:

```text
dbo.vw_openfda_ml_predictions
dbo.vw_openfda_analytics
dbo.vw_openfda_feature_importance
dbo.vw_openfda_anomalies
```

This separates:

```text
ADLS storage
      ↓
SQL serving
      ↓
BI consumption
```

Power BI connects to the Synapse serving layer rather than directly embedding the transformation logic.

---

## 14. Power BI

Power BI Desktop provides the business-facing analytical layer.

The dashboard combines:

* openFDA analytical summaries
* ML prediction results
* model feature importance
* anomaly observations
* recorded ML metrics

The dashboard is intended for analytical exploration and model diagnostics.

It does not represent:

* clinical decision support
* patient monitoring
* clinical risk scoring
* causal inference
* real-time healthcare operations

---

## 15. Security and Governance

The project demonstrates several cloud-security principles:

### Identity and access

* Azure RBAC is used for resource access.
* Managed identity is used where supported.
* Synapse uses its managed identity for ADLS access.
* Secrets are not committed to Git.
* GitHub Actions uses read-only repository permissions for validation.

### Data handling

The project uses public and synthetic data only.

No real patient records or PHI are intentionally used.

### Data governance

The lakehouse separates:

```text
RAW
BRONZE
SILVER
GOLD
ML
```

This makes processing stages and ownership boundaries explicit.

Streaming validation also provides a quarantine path for malformed events.

See [`docs/security-governance.md`](docs/security-governance.md).

---

## 16. CI/CD

GitHub Actions provides automated repository validation.

### Continuous Integration

CI runs on pushes and pull requests and performs:

```text
Checkout
   ↓
Python setup
   ↓
Dependency installation
   ↓
Python compilation
   ↓
Whitespace validation
   ↓
pytest
```

### Controlled Release Validation

The CD workflow is intentionally manual.

It validates a selected branch, tag, or commit without recreating or destroying Azure infrastructure.

This reflects the current implementation boundary: application/data-engineering validation is automated, while the existing Azure environment was provisioned incrementally.

---

## 17. Infrastructure as Code

Terraform is included as an infrastructure-as-code foundation.

Current Terraform scope includes:

* AzureRM provider configuration
* version constraints
* project environment variables
* environment outputs
* infrastructure documentation

The current Terraform configuration does **not** manage or recreate the existing Azure resources.

This is intentional.

Terraform has been validated with:

```bash
terraform init
terraform fmt
terraform validate
```

Future infrastructure management could progressively introduce resource blocks and import existing resources under Terraform control.

See [`infra/terraform/README.md`](infra/terraform/README.md).

---

## 18. Architecture Decisions

Major architecture decisions are documented in:

[`docs/architecture-decisions.md`](docs/architecture-decisions.md)

Individual Architecture Decision Records are maintained under:

```text
docs/adr/
```

Current ADRs cover topics including:

* ADLS architecture
* Event Hubs
* batch versus streaming
* historical replay versus live API
* Databricks Free Edition integration
* dbt runtime decision
* openFDA batch ingestion

The project deliberately avoids creating ADRs for minor implementation details.

---

## 19. Repository Structure

```text
healthcare-public-health-lakehouse/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
│
├── data/
│   └── fixtures/
│
├── docs/
│   ├── adr/
│   ├── architecture.md
│   ├── architecture-decisions.md
│   ├── data-contract.md
│   ├── data-sources.md
│   ├── databricks-integration.md
│   ├── day4-cdc-streaming.md
│   ├── day7-power-bi-serving.md
│   └── security-governance.md
│
├── infra/
│   └── terraform/
│       ├── main.tf
│       ├── outputs.tf
│       ├── README.md
│       ├── variables.tf
│       └── versions.tf
│
├── ingestion/
│
├── notebooks/
│   └── Day6_OpenFDA_ML.ipynb
│
├── scripts/
│
├── tests/
│
├── transformations/
│   ├── silver/
│   ├── gold/
│   └── ml/
│
├── requirements.txt
└── README.md
```

---

## 20. Current Azure Environment

| Component            | Resource                 |
| -------------------- | ------------------------ |
| Resource Group       | `rg-lakehouse-portfolio` |
| Region               | Southeast Asia           |
| ADLS Gen2            | `stlakehousebello`       |
| ADLS filesystem      | `healthcare`             |
| Event Hubs Namespace | `eh-lakehouse-bello`     |
| Event Hub            | `healthcare-events`      |
| Event Hub partitions | 4                        |
| Event retention      | 7 days                   |
| Data Factory         | `adf-lakehouse-bello`    |
| Synapse Workspace    | `syn-lakehouse-bello`    |
| Synapse database     | `healthcare_analytics`   |

---

## 21. Engineering Outcomes

The completed project demonstrates practical experience with:

* batch ingestion
* streaming ingestion
* event-time versus ingestion-time handling
* duplicate detection
* quarantine handling
* API pagination
* medallion architecture
* Parquet-based analytical storage
* Python data transformation
* SQL serving
* Power BI
* machine-learning feature engineering
* XGBoost classification
* anomaly detection
* SHAP explainability
* MLflow experimentation
* security and governance documentation
* GitHub Actions CI/CD
* Terraform infrastructure foundations
* architecture decision records
* explicit platform-constraint documentation

---

## 22. Important Limitations

This is a portfolio engineering project rather than a production healthcare platform.

Known limitations include:

* CDC data is historical and replayed; it is not a live production feed.
* The project does not contain PHI.
* openFDA adverse-event reports are observational and do not establish causality.
* ML results are based on the project's available dataset and should not be generalized to a broader population.
* Databricks Free Edition prevents the fully automated ADLS integration that would be expected in a more capable production environment.
* Terraform currently provides an infrastructure foundation rather than full ownership of the deployed Azure environment.
* Enterprise security capabilities such as private networking, Key Vault integration, customer-managed keys, centralized SIEM, and Purview governance are not implemented in this portfolio environment.

These limitations are documented deliberately to distinguish demonstrated functionality from future production evolution.

---

## 23. Future Production Evolution

A production-oriented extension could introduce:

1. Enterprise Databricks with governed external locations.
2. Automated Databricks-to-ADLS orchestration.
3. Azure Key Vault for secret management.
4. Private endpoints and network isolation.
5. Managed identities across additional services.
6. Centralized monitoring and alerting.
7. Microsoft Purview for enterprise data governance.
8. Expanded automated data-quality monitoring.
9. Full Terraform management of Azure infrastructure.
10. Automated ML retraining and model registry workflows.
11. CI/CD promotion across development, test, and production environments.

These are future capabilities, not claims about the current implementation.

---

## 24. Project Documentation

| Document                                                           | Purpose                                 |
| ------------------------------------------------------------------ | --------------------------------------- |
| [`docs/architecture.md`](docs/architecture.md)                     | Detailed system architecture            |
| [`docs/architecture-decisions.md`](docs/architecture-decisions.md) | Cross-cutting architecture rationale    |
| [`docs/data-contract.md`](docs/data-contract.md)                   | Streaming event contract                |
| [`docs/data-sources.md`](docs/data-sources.md)                     | Source and ingestion documentation      |
| [`docs/day4-cdc-streaming.md`](docs/day4-cdc-streaming.md)         | CDC streaming implementation            |
| [`docs/day7-power-bi-serving.md`](docs/day7-power-bi-serving.md)   | Synapse and Power BI serving            |
| [`docs/databricks-integration.md`](docs/databricks-integration.md) | ML environment and integration boundary |
| [`docs/security-governance.md`](docs/security-governance.md)       | Security and governance controls        |
| [`docs/adr/`](docs/adr/)                                           | Architecture Decision Records           |
| [`infra/terraform/README.md`](infra/terraform/README.md)           | Terraform infrastructure foundation     |

---

## 25. Final Summary

This project demonstrates an end-to-end healthcare/public-health data platform built around Azure lakehouse patterns.

It combines:

```text
Batch + Streaming
       ↓
ADLS Gen2
       ↓
Bronze → Silver → Gold
       ↓
Synapse Serverless
       ↓
Power BI
```

with a separate ML workflow:

```text
ADLS ML Features
       ↓
Databricks
       ↓
XGBoost + SHAP + Isolation Forest + MLflow
       ↓
ML Outputs
       ↓
ADLS ML Layer
       ↓
Synapse
       ↓
Power BI
```

The project emphasizes not only implementation, but also **data quality, security, governance, reproducibility, testing, architecture decisions, CI/CD, infrastructure-as-code, and transparent documentation of platform limitations**.

Where capabilities are not fully implemented, they are explicitly identified as future evolution rather than represented as completed production functionality.
