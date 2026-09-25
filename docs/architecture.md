# Healthcare Public Health Surveillance & Risk Analytics Lakehouse

## 1. Architecture Overview

This project implements a healthcare/public-health analytics platform combining:

* batch ingestion
* simulated streaming ingestion
* cloud data-lake storage
* data-quality validation
* medallion-style transformation
* SQL serving
* business intelligence
* machine learning
* infrastructure-as-code foundations
* CI/CD validation

The architecture intentionally separates:

* ingestion
* orchestration
* storage
* data quality
* transformation
* SQL serving
* business intelligence
* machine learning
* infrastructure provisioning
* application/code validation

Each component has a defined responsibility so that the platform can be extended without making one service responsible for the entire data lifecycle.

The project uses only public and synthetic data. No PHI is used.

---

## 2. High-Level Architecture

```text
                         PUBLIC / SYNTHETIC DATA
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
                    ▼                            ▼
             BATCH INGESTION              STREAM INGESTION
               openFDA API               Historical CDC replay
                    │                     accelerated cadence
                    ▼                            │
                   ADF                           ▼
             REST / HTTP                    Event Hubs
                    │                      Kafka protocol
                    ▼                            │
                ADLS RAW                    Python Consumer
                                                 │
                                                 ▼
                                            ADLS RAW
                    │                            │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                         DATA QUALITY CONTROLS
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
                  BRONZE                   QUARANTINE
                     │
                     ▼
                  SILVER
                     │
                     ▼
                   GOLD
                     │
             ┌───────┴──────────────┐
             │                      │
             ▼                      ▼
      Synapse Serverless       ML Feature Layer
             │                      │
             │                      ▼
             │              Databricks Free Edition
             │                      │
             │             ┌────────┴────────┐
             │             │                 │
             │             ▼                 ▼
             │        XGBoost ML       Isolation Forest
             │             │                 │
             │             └────────┬────────┘
             │                      │
             │                      ▼
             │                 ML Outputs
             │                      │
             │              Manual ADLS Handoff
             │                      │
             │                      ▼
             └──────────────► Synapse Serverless
                                    │
                                    ▼
                                 Power BI


        ┌──────────────────────────────────────────┐
        │ Supporting Engineering Controls          │
        │                                          │
        │ GitHub Actions CI/CD                     │
        │ pytest / validation tests                │
        │ Terraform IaC foundation                 │
        │ Security & governance controls            │
        │ Architecture Decision Records             │
        └──────────────────────────────────────────┘
```

---

# 3. Azure Infrastructure

## 3.1 Resource Group

```text
rg-lakehouse-portfolio
```

The resource group provides the logical Azure boundary for the project environment.

---

## 3.2 Azure Data Lake Storage Gen2

Primary project storage:

```text
stlakehousebello
```

Filesystem:

```text
healthcare/
```

Canonical project structure:

```text
healthcare/
├── raw/
│   ├── cdc/
│   └── openfda/
├── bronze/
│   ├── cdc/
│   └── openfda/
├── silver/
│   ├── cdc/
│   └── openfda/
├── gold/
│   ├── cdc/
│   └── openfda/
├── quarantine/
│   └── cdc/
└── ml/
    └── openfda/
```

ADLS Gen2 provides the common storage boundary for ingestion, transformation outputs, analytical datasets and ML outputs.

---

## 3.3 Azure Event Hubs

Namespace:

```text
eh-lakehouse-bello
```

Event Hub:

```text
healthcare-events
```

Configuration used by the project:

```text
Partitions: 4
Retention: 7 days
Protocol: Kafka-compatible interface
```

Event Hubs provides the streaming ingestion endpoint.

The project uses the Kafka-compatible interface to demonstrate interoperability with Python Kafka tooling without introducing a separate Kafka cluster.

---

## 3.4 Azure Data Factory

Factory:

```text
adf-lakehouse-bello
```

Azure Data Factory is used for **batch ingestion orchestration**.

The implemented openFDA pipeline uses:

```text
openFDA REST API
       ↓
ADF REST dataset
       ↓
Parameterized pagination
       ↓
ADLS Gen2 RAW
```

ADF responsibilities include:

* REST API connectivity
* parameterized pagination
* batch ingestion orchestration
* scheduling
* pipeline execution monitoring
* source-to-RAW movement

ADF does not currently orchestrate the full downstream transformation and ML lifecycle.

Python and Databricks are used separately for transformation and ML workloads.

---

## 3.5 Synapse Serverless

Workspace:

```text
syn-lakehouse-bello
```

Database:

```text
healthcare_analytics
```

Synapse Serverless SQL provides SQL-based access to analytical files stored in ADLS.

A Dedicated SQL Pool is intentionally not used.

The project uses Synapse Serverless to expose analytical and ML outputs without introducing a continuously running dedicated warehouse.

---

# 4. Data Ingestion

## 4.1 openFDA Batch Ingestion

The project uses the public openFDA adverse-event API as a batch source.

The implemented ingestion architecture is:

```text
openFDA API
     ↓
Azure Data Factory
     ↓
Parameterized REST pagination
     ↓
ADLS Gen2 RAW
```

The ADF pipeline uses four API pages during the demonstrated ingestion run:

```text
skip=0
skip=1000
skip=2000
skip=3000
```

Validation of the four-page test produced:

```text
API response pages:       4
Total reports:            4,000
Unique safetyreportid:    4,000
Duplicate reports:        0
First safetyreportid:     5801206-7
Last safetyreportid:      10007321
```

The final ADF copy activity produced one combined RAW JSON file.

The `rowsRead=4` value from the ADF activity output represents the four paginated API responses, not four individual adverse-event reports.

The ADF pipeline also has a daily scheduled trigger configured for the Kuala Lumpur/Singapore timezone.

The current sink uses a fixed RAW filename; future production hardening could introduce run- or date-partitioned output paths to prevent scheduled runs from overwriting a previous snapshot.

---

## 4.2 CDC Historical Streaming Replay

The streaming workload uses the archived public CDC dataset:

```text
Weekly United States COVID-19 Cases and Deaths by State - ARCHIVED
Dataset ID: pwn4-m3yp
```

The original dataset is historical and discontinued.

Therefore, this project does **not** describe the source as a live CDC feed.

Instead:

> Historical public-health surveillance data is replayed at an accelerated cadence to simulate near-real-time event arrival, while preserving event-time and ingestion-time metadata and injecting synthetic faults for validation.

The flow is:

```text
CDC historical fixture
        ↓
Python replay producer
        ↓
Kafka protocol
        ↓
Azure Event Hubs
        ↓
Python consumer
        ↓
ADLS RAW
        ↓
Validation
        ├── Bronze
        └── Quarantine
```

The streaming event envelope contains:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

The `event_id` is deterministically generated from:

```text
state | start_date | end_date
```

using SHA-256.

This allows the same business event to produce the same identifier when delivered more than once.

---

# 5. Data Lake Medallion Layers

The project uses a Raw → Bronze → Silver → Gold pattern, with a separate ML output layer.

---

## 5.1 RAW

The RAW layer preserves source-oriented data before analytical transformation.

Purpose:

* source preservation
* traceability
* replayability
* auditability
* recovery from downstream transformation errors

Examples:

```text
healthcare/raw/openfda/
healthcare/raw/cdc/
```

---

## 5.2 BRONZE

Bronze contains validated ingestion outputs prepared for downstream transformation.

For the CDC streaming workload, accepted events retain important operational metadata:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

Malformed events are not promoted into Bronze.

---

## 5.3 QUARANTINE

Invalid records are separated from accepted records.

Example:

```text
healthcare/quarantine/cdc/
```

The final CDC replay validation produced:

```text
RAW events:          1,002
Bronze events:       1,000
Quarantined events:      1
```

The quarantined event failed validation because the required `event_time` field was missing.

A duplicate delivery was also intentionally injected during the replay workload. Deterministic event IDs allow duplicate business events to be identified separately from malformed records.

---

## 5.4 SILVER

Silver contains cleaned and standardized datasets.

Processing includes:

* schema normalization
* type conversion
* null handling
* duplicate handling
* standardization
* derived fields
* business-rule validation

CDC Silver:

```text
1,000 rows
15 columns
```

with deduplication based on `event_id`.

OpenFDA Silver consists of separate analytical entities:

```text
adverse_events.parquet
adverse_event_reactions.parquet
adverse_event_drugs.parquet
```

Recorded outputs:

```text
adverse_events:          1,000 rows × 17 columns
adverse_event_reactions: 2,749 rows × 4 columns
adverse_event_drugs:     3,079 rows × 13 columns
```

No duplicate `safetyreportid` values were present in the validated adverse-event report dataset.

---

## 5.5 GOLD

Gold contains curated analytical datasets with explicitly defined grains.

CDC Gold:

```text
1,000 rows
11 columns
60 states
```

The CDC analytical layer includes derived measures such as case/death relationships while preserving the distinction between event-time and ingestion-time processing.

OpenFDA Gold:

```text
78 rows
9 columns
34 reporter countries
1,000 total reports
```

The OpenFDA Gold grain is:

```text
reporter_country + transmission_date
```

The dataset contains analytical measures including:

* adverse-event report counts
* serious-report counts
* death-report counts
* expedited-report counts
* serious-report percentage
* death-report percentage
* expedited-report percentage

These are descriptive reporting metrics and are not interpreted as causal measures of drug safety.

---

# 6. Transformation Architecture

Transformations are implemented primarily in Python using Pandas and PyArrow.

Key transformation modules include:

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

Parquet is used for analytical outputs because it provides:

* typed columns
* columnar storage
* compression
* efficient analytical reads
* interoperability across Python, Spark/Databricks and SQL-serving tools

---

# 7. Data Quality Architecture

Data quality is treated as an engineering control rather than an afterthought.

Validation exists at multiple levels.

## Streaming validation

The CDC streaming path validates:

* required event fields
* event ID presence
* timestamp presence
* schema conformity
* duplicate business identifiers
* source metadata
* quarantine conditions

Conceptually:

```text
                 Incoming Event
                       │
                       ▼
                Validation Gate
                  ┌────┴────┐
                  │         │
                Valid     Invalid
                  │         │
                  ▼         ▼
               Bronze   Quarantine
```

---

## Repository-level validation

The repository contains automated tests covering areas such as:

* deterministic event ID generation
* required CDC fields
* null validation
* event ID uniqueness
* duplicate detection
* CDC Gold grain
* Silver-to-Gold reconciliation
* OpenFDA `safetyreportid` uniqueness
* ML target validity
* ML leakage controls
* serving-layer documentation

The full local test suite passed during Day 8 validation.

---

# 8. Synapse Serverless Serving Layer

Synapse Serverless provides SQL-based access to analytical files in ADLS.

The project uses a managed identity for the Synapse workspace to access the project storage boundary.

The serving database is:

```text
healthcare_analytics
```

Important views include:

```text
dbo.vw_openfda_analytics
dbo.vw_openfda_ml_predictions
dbo.vw_openfda_feature_importance
dbo.vw_openfda_anomalies
```

These views provide a stable SQL interface between lake-based analytical outputs and Power BI.

This separates storage and transformation concerns from the business-facing reporting layer.

---

# 9. Machine Learning Architecture

The ML workload focuses on **OpenFDA adverse-event analytics**.

It contains two complementary analytical components:

1. supervised seriousness classification
2. unsupervised anomaly screening

The ML feature engineering module is:

```text
transformations/ml/openfda_features.py
```

The generated ML feature dataset contains:

```text
1,000 rows
13 columns
```

Important engineered features include:

```text
number_of_reactions
number_of_drugs
transmission_year
transmission_month
reporting_delay_days
target_serious
drug_reaction_ratio
```

Potential leakage fields such as:

```text
seriousnessdeath
fulfillexpeditecriteria
patientdeathdate
companynumb
```

are excluded from model features.

The report identifier is retained for traceability but is not used as a predictive feature.

---

# 10. Databricks ML Execution

Databricks Free Edition is used as a separate ML execution environment.

The project uses a managed Unity Catalog volume:

```text
/Volumes/workspace/default/openfda_ml/
```

The ML workflow includes:

```text
ADLS / local ML feature preparation
              ↓
       Databricks ML
              ↓
       XGBoost model
              ↓
     ML predictions
              ↓
     Isolation Forest
              ↓
     anomaly outputs
              ↓
       ML diagnostics
```

The project also uses SHAP-based explainability and MLflow capabilities within the ML experimentation workflow.

### Free Edition integration boundary

Databricks Free Edition does not provide the required unrestricted external ADLS integration configuration for this project.

Therefore, the current implementation uses a **controlled manual handoff** from the Databricks-managed environment back into the canonical ADLS ML layer.

The project does not claim fully automated Databricks-to-ADLS orchestration.

The canonical ML outputs are:

```text
healthcare/ml/openfda/
├── openfda_ml_features.parquet
├── openfda_ml_predictions.parquet
├── openfda_feature_importance.parquet
└── openfda_anomalies.parquet
```

This limitation is documented in:

```text
docs/databricks-integration.md
docs/adr/ADR-005-databricks-free-edition-integration.md
```

---

# 11. ML Model Results

The XGBoost seriousness-classification experiment was evaluated on a 200-row holdout set.

Recorded metrics:

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

The majority-class baseline accuracy was approximately:

```text
0.545
```

These results demonstrate the mechanics of an ML analytics workflow but should not be interpreted as clinical performance.

The dataset is relatively small and is not intended to establish a production-ready predictive model.

---

# 12. Anomaly Detection

Isolation Forest is used to identify observations with unusual feature patterns.

Configuration used for the demonstrated experiment:

```text
n_estimators = 200
contamination = 0.05
random_state = 42
n_jobs = -1
```

The model was applied to the 200-row holdout set.

Recorded result:

```text
Validated rows:       200
Detected anomalies:   10
```

Anomaly outputs contain:

```text
safetyreportid
anomaly_prediction
anomaly_score
is_anomaly
```

The anomaly model is a screening mechanism.

It does not indicate:

* fraud
* causality
* clinical risk
* medical diagnosis
* confirmed data quality failure

---

# 13. Power BI Architecture

Power BI provides the business-facing analytical layer.

The general serving flow is:

```text
ADLS analytical outputs
        ↓
Synapse Serverless
        ↓
SQL views
        ↓
Power BI
```

Power BI consumes:

* CDC analytical outputs
* OpenFDA analytical outputs
* ML predictions
* feature importance
* anomaly results
* ML evaluation metrics

The ML dashboard includes:

```text
FACT_OPENFDA_FEATURE_IMPORTANCE
FACT_OPENFDA_ANOMALIES
ML Metrics
```

The dashboard presents ML outputs as analytical diagnostics rather than clinical decision support.

For example, anomaly visualizations are framed as:

> Isolation Forest identifies observations with unusual feature patterns for review. It does not indicate fraud, causality, or clinical risk.

OpenFDA metrics are similarly interpreted as reporting-pattern analytics rather than evidence of causal drug safety effects.

---

# 14. Security and Governance

The project applies several security and governance principles.

## Identity and access

* Azure RBAC is used for data-lake access.
* Managed identity is used for Synapse access to ADLS.
* ADF uses secured parameter handling for the openFDA API key.
* Secrets and connection strings are not committed to Git.
* GitHub Actions uses read-only repository permissions for validation workflows.

## Data classification

The project uses:

* public openFDA data
* archived public CDC data
* synthetic test/replay data

No PHI is introduced into the portfolio environment.

## Data governance

Important governance controls include:

* source preservation in RAW
* validation before analytical promotion
* quarantine of malformed records
* deterministic event identifiers
* preservation of event-time and ingestion-time
* ML leakage controls
* explicit ML limitations
* controlled serving-layer access

Known production-hardening areas not implemented in this portfolio environment include:

* Azure Key Vault integration
* private endpoints
* VNet isolation
* customer-managed encryption keys
* Microsoft Purview governance
* enterprise SIEM integration
* production-grade Databricks external locations

These are documented limitations rather than implied capabilities.

---

# 15. CI/CD and Engineering Controls

GitHub Actions provides repository-level CI/CD validation.

## Continuous Integration

CI validates:

* Python compilation
* repository formatting/whitespace
* automated tests
* transformation and application code

The CI workflow runs automatically on relevant pushes and pull requests.

## Controlled Release Validation

CD is implemented as a manually triggered release-validation workflow.

It validates:

* the selected release reference
* Python environment
* repository formatting
* Python compilation
* full test suite

The current CD workflow does not automatically create or destroy Azure infrastructure.

This separation prevents the project from claiming automated infrastructure deployment that has not been implemented.

---

# 16. Terraform Infrastructure-as-Code Foundation

Terraform is included as an infrastructure-as-code foundation.

Current structure:

```text
infra/terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── README.md
└── .terraform.lock.hcl
```

The current Terraform configuration intentionally contains no Azure resource blocks.

Therefore:

```text
Terraform
   │
   ├── provider configuration
   ├── environment variables
   ├── outputs
   └── validation
```

rather than:

```text
Terraform
   │
   └── full Azure resource ownership
```

The existing Azure environment was provisioned incrementally during project development.

Future infrastructure management could selectively import existing resources or deliberately recreate resources under Terraform control after appropriate validation.

---

# 17. Architecture Principles

The architecture is based on a small number of deliberate principles:

1. ADLS Gen2 provides the common lake storage boundary.
2. Batch and streaming workloads use patterns appropriate to their operational characteristics.
3. Historical CDC replay provides a reproducible streaming workload without claiming a live production CDC source.
4. ADF handles openFDA batch orchestration.
5. Event Hubs provides the streaming ingestion endpoint.
6. Python provides explicit transformation and streaming-validation logic.
7. Parquet provides the analytical storage format.
8. Synapse Serverless provides SQL-based serving over the lake.
9. Databricks Free Edition provides a separate ML execution environment within its platform constraints.
10. The controlled Databricks → ADLS handoff is documented as a workaround rather than presented as production orchestration.
11. Terraform establishes an infrastructure-as-code foundation without falsely claiming full management of the existing environment.
12. GitHub Actions validates application and data-engineering code separately from infrastructure provisioning.
13. Public and synthetic data are used to avoid introducing PHI into the portfolio environment.

---

# 18. Service Responsibility Matrix

| Capability          | Technology                                      | Responsibility                            |
| ------------------- | ----------------------------------------------- | ----------------------------------------- |
| Batch ingestion     | Azure Data Factory                              | openFDA REST ingestion and scheduling     |
| Streaming endpoint  | Azure Event Hubs                                | Event ingestion                           |
| Streaming producer  | Python                                          | Historical CDC replay                     |
| Streaming consumer  | Python                                          | Validation and ADLS persistence           |
| Data lake           | ADLS Gen2                                       | Canonical storage                         |
| Data transformation | Python / Pandas / PyArrow                       | Silver and Gold processing                |
| SQL serving         | Synapse Serverless                              | SQL access over lake data                 |
| ML execution        | Databricks Free Edition                         | Model training and analytics              |
| ML modeling         | XGBoost / Isolation Forest                      | Classification and anomaly screening      |
| Explainability      | SHAP                                            | Feature-level model diagnostics           |
| Experiment tracking | MLflow                                          | ML experiment/model tracking capabilities |
| BI                  | Power BI                                        | Business-facing analytics                 |
| Code validation     | GitHub Actions / pytest                         | Automated repository validation           |
| IaC foundation      | Terraform                                       | Infrastructure-as-code foundation         |
| Governance          | Azure RBAC / managed identities / documentation | Access and security controls              |

---

# 19. Current Architecture Status

| Area                                        | Status                                      |
| ------------------------------------------- | ------------------------------------------- |
| ADLS Gen2                                   | Implemented                                 |
| Event Hubs                                  | Implemented                                 |
| Kafka-compatible streaming                  | Implemented                                 |
| Historical CDC replay                       | Implemented                                 |
| CDC validation/quarantine                   | Implemented                                 |
| openFDA ADF ingestion                       | Implemented                                 |
| openFDA pagination                          | Implemented and validated                   |
| Silver transformations                      | Implemented                                 |
| Gold transformations                        | Implemented                                 |
| Synapse Serverless serving                  | Implemented                                 |
| Power BI serving                            | Implemented                                 |
| OpenFDA ML feature engineering              | Implemented                                 |
| XGBoost seriousness classification          | Implemented                                 |
| Isolation Forest anomaly screening          | Implemented                                 |
| SHAP diagnostics                            | Implemented                                 |
| MLflow workflow                             | Implemented within ML experimentation scope |
| Databricks → ADLS automation                | Not implemented due Free Edition constraint |
| Security/governance documentation           | Implemented                                 |
| CI validation                               | Implemented                                 |
| Controlled CD validation                    | Implemented                                 |
| Terraform foundation                        | Implemented                                 |
| Full Terraform Azure resource management    | Not implemented                             |
| Production-grade network/security hardening | Not implemented                             |

---

# 20. Architecture Evolution

The current architecture is intentionally suitable for a portfolio environment while documenting how it could evolve.

A future production-oriented implementation could introduce:

```text
Current
   │
   ├── Databricks Free Edition
   │
   ├── Manual ML output handoff
   │
   ├── Terraform foundation
   │
   └── Public/synthetic data
   │
   ▼
Potential Production Evolution
   │
   ├── Enterprise Databricks workspace
   ├── Automated ADLS external locations
   ├── Managed orchestration across ingestion/ML
   ├── Full Terraform resource management
   ├── Azure Key Vault
   ├── Private networking
   ├── Centralized monitoring
   ├── Data catalog/governance
   └── Production identity and security controls
```

These future capabilities are architectural evolution options and are not represented as currently implemented features.

---

# 21. Related Documentation

### Architecture decisions

```text
docs/architecture-decisions.md
```

Provides the consolidated rationale for the major architectural decisions.

### Architecture Decision Records

```text
docs/adr/
```

Contains the detailed decision records:

```text
ADR-001-adls.md
ADR-002-event-hubs.md
ADR-003-batch-vs-streaming.md
ADR-004-replay-vs-live-api.md
ADR-005-databricks-free-edition-integration.md
ADR-006-dbT-runtime-decision.md
ADR-007-openfda-batch-ingestion.md
```

### Data documentation

```text
docs/data-sources.md
docs/data-contract.md
```

### ML documentation

```text
docs/databricks-integration.md
```

### Security

```text
docs/security-governance.md
```

### Power BI and serving

```text
docs/day7-power-bi-serving.md
```

### Terraform

```text
infra/terraform/README.md
```

---

# 22. Final Architecture Summary

The implemented platform separates batch and streaming ingestion while using ADLS Gen2 as the common storage boundary.

```text
openFDA
   │
   ▼
ADF
   │
   ▼
ADLS
   │
   ├── Bronze
   ├── Silver
   └── Gold
          │
          ▼
     Synapse Serverless
          │
          ▼
       Power BI


Historical CDC
      │
      ▼
Python Replay
      │
      ▼
Event Hubs
      │
      ▼
Python Consumer
      │
      ▼
ADLS
      │
      ├── Bronze
      ├── Silver
      ├── Gold
      └── Quarantine


OpenFDA ML Features
      │
      ▼
Databricks Free Edition
      │
      ├── XGBoost
      ├── SHAP
      └── Isolation Forest
      │
      ▼
Controlled ML Output Handoff
      │
      ▼
ADLS ML
      │
      ▼
Synapse Serverless
      │
      ▼
Power BI
```

The architecture demonstrates practical data-engineering patterns across ingestion, streaming, lakehouse storage, transformation, data quality, SQL serving, BI, machine learning, governance, CI/CD and infrastructure-as-code.

Where platform limitations or incomplete production capabilities exist, they are explicitly documented rather than represented as implemented functionality.
