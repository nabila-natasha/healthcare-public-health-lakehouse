# Healthcare Public Health Surveillance & Risk Analytics Lakehouse

## 1. Architecture Overview

This project implements a healthcare and public-health analytics platform combining:

* Batch ingestion
* Simulated streaming ingestion
* Cloud data-lake storage
* Medallion data processing
* Data-quality validation
* SQL-based analytical serving
* Business intelligence
* Machine learning
* Infrastructure-as-code foundations
* CI/CD validation

The architecture separates ingestion, orchestration, storage, transformation, data quality, analytical serving, business intelligence, and machine learning responsibilities.

The design intentionally reflects the capabilities and constraints of the selected Azure and Databricks environments.

The project uses public openFDA data and synthetic/historical public-health data. It does not use PHI or patient-identifiable clinical records.

---

## 2. High-Level Architecture

```text
                         BUSINESS REQUIREMENTS
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
                    ▼                            ▼
             BATCH INGESTION              STREAM INGESTION
               openFDA API                Historical CDC data
                    │                     accelerated replay
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
                                  ▼
                         DATA QUALITY VALIDATION
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
             ┌───────┴────────┐
             │                │
             ▼                ▼
      Synapse Serverless   ML-ready data
             │                │
             ▼                ▼
        Power BI       Databricks Free Edition
                              │
                              ▼
                         ML predictions
                         Feature importance
                         Anomalies
                              │
                       controlled handoff
                              │
                              ▼
                         ADLS ML layer
                              │
                              ▼
                      Synapse Serverless
                              │
                              ▼
                          Power BI
```

The Azure data-engineering path remains independent of Databricks Free Edition.

Databricks is used as a separate ML execution environment because the selected Free Edition environment does not provide the same Azure storage connectivity model as a provisioned Azure Databricks deployment.

---

## 3. Azure Infrastructure

### 3.1 Resource Group

```text
rg-lakehouse-portfolio
```

The resource group provides the logical boundary for the project's Azure resources.

### 3.2 ADLS Gen2

Primary project storage:

```text
stlakehousebello
```

The project uses the `healthcare` filesystem:

```text
healthcare/
├── raw/
├── bronze/
├── silver/
├── gold/
├── quarantine/
└── ml/
```

ADLS Gen2 acts as the canonical storage boundary for the Azure data-engineering pipeline.

### 3.3 Event Hubs

Namespace:

```text
eh-lakehouse-bello
```

Event Hub:

```text
healthcare-events
```

Configuration used by the project:

* Standard tier
* Four partitions
* Seven-day message retention
* Kafka-compatible interface

Event Hubs provides the streaming ingestion endpoint for the historical CDC replay workload.

### 3.4 Azure Data Factory

Factory:

```text
adf-lakehouse-bello
```

ADF is used for batch ingestion and cloud orchestration.

The implemented openFDA pipeline uses:

```text
openFDA REST API
       │
       ▼
ADF REST / HTTP
       │
       ▼
ADLS RAW
```

The pipeline includes parameterized API pagination and writes the resulting data to the canonical RAW layer.

### 3.5 Synapse Serverless

Workspace:

```text
syn-lakehouse-bello
```

Synapse Serverless SQL provides SQL-based access to files stored in ADLS.

The project uses a serverless SQL model rather than a continuously provisioned Dedicated SQL Pool.

---

# 4. Data Ingestion

## 4.1 Batch Ingestion — openFDA

The openFDA adverse-event API is ingested using Azure Data Factory.

Implemented flow:

```text
openFDA API
     │
     ▼
ADF REST / HTTP
     │
     ▼
ADLS RAW
     │
     ▼
Bronze
     │
     ▼
Silver
     │
     ▼
Gold
```

The final ADF ingestion validated four paginated API responses containing:

* 4,000 adverse-event reports
* 4,000 unique `safetyreportid` values
* Zero duplicate report IDs in the validation sample

The ADF pipeline uses parameterized pagination rather than treating the API as a single unbounded request.

The RAW layer preserves the ingested source response before transformation.

---

## 4.2 Streaming Ingestion — Historical CDC Replay

The streaming workload uses the archived CDC dataset:

```text
Weekly United States COVID-19 Cases and Deaths by State - ARCHIVED
Dataset ID: pwn4-m3yp
```

The source is historical rather than genuinely real-time.

Historical records are replayed at an accelerated cadence to simulate near-real-time event arrival.

Implemented flow:

```text
CDC historical fixture
        │
        ▼
Python replay producer
        │
        ▼
Azure Event Hubs
Kafka protocol
        │
        ▼
Python consumer
        │
        ▼
ADLS RAW
        │
        ▼
Bronze
```

Each event preserves:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

The replay workload also injects controlled faults to validate the pipeline, including duplicate delivery and malformed events.

The final Day 4 validation recorded:

```text
RAW events:          1002
Bronze events:       1000
Quarantined events:     1
```

Invalid records are not allowed to silently enter the accepted Bronze dataset.

---

# 5. Data Lake Layers

The project follows a medallion-style architecture.

## 5.1 Raw

The RAW layer preserves source data with minimal modification.

Purpose:

* Source preservation
* Traceability
* Replayability
* Ingestion auditing

```text
healthcare/raw/
```

Examples:

```text
healthcare/raw/openfda/openfda_adverse_events.json
healthcare/raw/cdc/<replay-run>/
```

---

## 5.2 Bronze

Bronze contains validated ingestion outputs prepared for downstream processing.

```text
healthcare/bronze/
```

For streaming data, the event envelope preserves operational metadata such as:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

Duplicate event IDs and malformed records are handled according to the pipeline validation rules.

---

## 5.3 Silver

Silver contains cleaned and standardized records.

Typical processing includes:

* Schema normalization
* Type conversion
* Null handling
* Duplicate handling
* Standardization
* Derived fields
* Data-quality validation

The project uses Parquet for Silver datasets.

Examples include:

```text
healthcare/silver/openfda/
healthcare/silver/cdc/
```

---

## 5.4 Gold

Gold contains curated analytical datasets with explicitly defined grains and metrics.

```text
healthcare/gold/
```

Examples include:

```text
healthcare/gold/openfda/openfda_gold.parquet
healthcare/gold/cdc/
```

Gold datasets are designed for analytical consumption rather than simply copying Silver data.

---

## 5.5 Quarantine

Records that fail validation are separated from accepted records.

```text
healthcare/quarantine/
```

This prevents malformed or invalid records from silently entering downstream analytical datasets.

The CDC streaming workload demonstrated this pattern using a malformed event with a missing required `event_time`.

---

## 5.6 ML

The ML layer stores model-related datasets and outputs.

```text
healthcare/ml/openfda/
```

Current outputs include:

```text
openfda_ml_features.parquet
openfda_ml_predictions.parquet
openfda_feature_importance.parquet
openfda_anomalies.parquet
```

These outputs are analytical model artifacts and are not treated as clinical decisions.

---

# 6. Data Quality

Data quality is treated as a pipeline control rather than an afterthought.

Validation is implemented through both transformation-level checks and automated repository tests.

Key controls include:

* Required-field validation
* Schema validation
* Timestamp validation
* Duplicate detection
* Event ID validation
* Source metadata validation
* Gold-grain validation
* Source-to-target reconciliation
* OpenFDA report ID uniqueness
* ML target validation
* ML leakage exclusion checks

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

The CDC event ID is deterministic.

It is generated from:

```text
state|start_date|end_date
```

using SHA-256.

This allows repeated delivery of the same business event to be identified by the same event ID while preserving a separate `ingestion_time`.

---

# 7. Transformation Architecture

The project uses Python and Pandas/PyArrow for the primary local transformation workflows.

The transformation path is:

```text
Bronze
  │
  ▼
Python transformation
  │
  ▼
Silver
  │
  ▼
Python transformation
  │
  ▼
Gold
```

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

Parquet is used for analytical datasets because it provides typed columns, columnar storage, compression, and efficient downstream analytical access.

---

# 8. Synapse Serverless

Synapse Serverless SQL is the SQL access and serving layer over ADLS.

Conceptually:

```text
ADLS
 │
 ├── Gold
 │
 └── ML
      │
      ▼
Synapse Serverless
      │
      ├── SQL validation
      ├── Analytical queries
      └── Power BI connectivity
```

The project uses the following openFDA ML serving views:

```text
dbo.vw_openfda_ml_predictions
dbo.vw_openfda_feature_importance
dbo.vw_openfda_anomalies
```

The Synapse layer allows downstream consumers to query analytical files without requiring a Dedicated SQL Pool.

---

# 9. Power BI

Power BI Desktop provides the business intelligence layer.

The implemented serving pattern is:

```text
ADLS
 │
 ▼
Synapse Serverless
 │
 ▼
Power BI Desktop
```

The dashboard can combine:

* Public-health trends
* Event volumes
* Regional patterns
* Data-quality indicators
* Operational latency
* openFDA analytical metrics
* ML predictions
* Feature importance
* Anomaly indicators

ML outputs are presented as analytical signals.

They are not presented as clinical decisions, causal findings, or confirmed safety risks.

For anomaly reporting, the interpretation is:

> Isolation Forest identifies observations with unusual feature patterns for review. It does not indicate fraud, causality, or clinical risk.

---

# 10. Databricks Free Edition

Databricks Free Edition is used as the ML and PySpark execution environment.

The primary notebook is:

```text
notebooks/Day6_OpenFDA_ML.ipynb
```

The implemented workflow includes:

* Feature engineering
* Categorical and numerical preprocessing
* XGBoost classification
* Model evaluation
* Feature importance
* Isolation Forest anomaly detection
* SHAP-based interpretation
* MLflow experiment/model tracking

The Databricks working storage boundary is:

```text
/Volumes/workspace/default/openfda_ml/
```

The resulting ML datasets are handed off to the canonical ADLS ML layer through a controlled manual process.

The architecture therefore does not claim fully automated direct ADLS integration from Databricks Free Edition.

The detailed implementation boundary is documented in:

```text
docs/databricks-integration.md
```

The formal architectural decision is recorded in:

```text
docs/adr/ADR-005-databricks-free-edition-integration.md
```

---

# 11. Machine Learning Architecture

The openFDA ML workflow is:

```text
OpenFDA Silver
      │
      ▼
Feature Engineering
      │
      ▼
ML Feature Dataset
      │
      ▼
Train / Test Split
      │
      ├───────────────┐
      ▼               ▼
   XGBoost      Isolation Forest
      │               │
      ▼               ▼
Predictions       Anomalies
      │
      ├───────────────┐
      ▼               ▼
Feature Importance    SHAP
      │
      ▼
Parquet Outputs
      │
      ▼
ADLS ML Layer
      │
      ▼
Synapse Serverless
      │
      ▼
Power BI
```

The XGBoost model was evaluated on a 200-row holdout sample.

Observed metrics:

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 0.7800 |
| Precision | 0.7831 |
| Recall    | 0.7143 |
| F1        | 0.7471 |
| ROC-AUC   | 0.8759 |
| PR-AUC    | 0.8803 |

The majority-class baseline accuracy was 0.545.

These results demonstrate the implemented ML workflow and should not be interpreted as production-level predictive performance.

The dataset is a project sample and is not assumed to represent the complete openFDA reporting population.

---

# 12. Infrastructure as Code

Terraform provides the infrastructure-as-code foundation.

Current structure:

```text
infra/
└── terraform/
```

The current Terraform configuration is intentionally a foundation rather than a complete recreation of the existing Azure environment.

The project environment was provisioned incrementally during development.

Existing resources are therefore not recreated or destroyed solely to place them under Terraform management.

Future infrastructure can be imported selectively into Terraform state where this provides operational value.

The Terraform foundation is intended to demonstrate:

* Infrastructure-as-code structure
* AzureRM provider usage
* Configuration separation
* Resource outputs and variables
* A path toward reproducible infrastructure management

---

# 13. CI/CD Architecture

GitHub Actions provides repository-level CI/CD validation.

## Continuous Integration

CI runs on:

* Pushes to `main`
* Pushes to feature branches
* Pull requests targeting `main`

CI performs:

```text
Checkout
   │
   ▼
Python setup
   │
   ▼
Dependency installation
   │
   ▼
Python compilation
   │
   ▼
Whitespace validation
   │
   ▼
pytest
```

The test suite validates transformation and data-quality logic without requiring the live Azure environment.

---

## Controlled Release Validation

CD is implemented as a manually triggered release-validation workflow.

It validates a selected branch, tag, or commit by running:

* Dependency installation
* Python compilation
* Whitespace validation
* Full repository tests
* GitHub release summary

The current CD workflow does not automatically recreate, modify, or destroy Azure infrastructure.

This is deliberate because the current Azure environment was provisioned incrementally and is documented separately from repository release validation.

---

# 14. Security and Governance

The project follows a least-privilege and identity-based access approach where supported by the environment.

Key controls include:

* Azure RBAC
* Managed identity for Synapse access to ADLS
* ADF managed identity for storage access where configured
* Secure handling of API credentials
* No secrets committed to Git
* GitHub Actions `contents: read` permission
* Data-layer separation
* Quarantine of invalid streaming events
* ML leakage controls
* Analytical rather than clinical interpretation of ML outputs

The project uses public and synthetic data.

It does not contain PHI or patient-identifiable clinical records.

The project does not currently implement enterprise controls such as:

* Azure Key Vault integration
* Private endpoints
* Customer-managed keys
* Full network isolation
* Microsoft Purview governance
* Enterprise SIEM integration

These are documented as production-evolution opportunities rather than claimed capabilities.

---

# 15. Service Responsibility Matrix

| Component               | Primary Responsibility                              |
| ----------------------- | --------------------------------------------------- |
| Azure Event Hubs        | Streaming event ingestion                           |
| Python producer         | Historical CDC event replay                         |
| Python consumer         | Kafka consumption, validation, and ADLS persistence |
| ADLS Gen2               | Canonical lake storage                              |
| Azure Data Factory      | Batch ingestion and cloud orchestration             |
| Python/Pandas/PyArrow   | Primary transformation processing                   |
| Databricks Free Edition | PySpark and ML experimentation/execution            |
| Synapse Serverless      | SQL querying, validation, and serving               |
| Power BI Desktop        | Business intelligence and visualization             |
| Terraform               | Infrastructure-as-code foundation                   |
| GitHub Actions          | CI/CD validation                                    |
| dbt                     | Not part of the core runtime                        |

---

# 16. Key Architecture Principles

## Separation of Concerns

Each component has a defined responsibility rather than being included simply to increase the number of technologies.

## Reproducibility

The streaming workload uses a deterministic historical replay fixture so that ingestion behavior and fault handling can be repeatedly tested.

## Data Lineage

The Raw → Bronze → Silver → Gold progression provides traceability through the analytical data lifecycle.

## Data Quality by Design

Invalid records are quarantined instead of being silently discarded.

## Identity-Based Access

Managed identities and RBAC are preferred over embedding long-lived storage credentials in pipeline configuration.

## Explicit Data Grain

Analytical datasets are designed around clearly defined grains rather than being treated as generic tables.

## Platform-Aware Design

The architecture explicitly accounts for the limitations of Databricks Free Edition instead of assuming that it provides the same integration capabilities as a provisioned Azure Databricks environment.

## Cost Awareness

The project deliberately avoids unnecessary infrastructure such as:

* AKS
* Virtual machines
* Dedicated Synapse SQL Pool
* Unnecessary monitoring stacks
* Private networking
* Additional Azure Databricks infrastructure

The architecture is designed around the available project environment and trial/free-resource constraints.

---

# 17. Current Architecture Status

The project has progressed from the initial Day 0 foundation to an implemented Day 8 portfolio architecture.

| Capability                                     | Status                                   |
| ---------------------------------------------- | ---------------------------------------- |
| ADLS Gen2                                      | Implemented and validated                |
| Event Hubs / Kafka                             | Implemented and validated                |
| CDC historical replay                          | Implemented and validated                |
| CDC Bronze / quarantine flow                   | Implemented and validated                |
| ADF openFDA ingestion                          | Implemented and validated                |
| openFDA Silver / Gold                          | Implemented and validated                |
| Data-quality test suite                        | Implemented and passing                  |
| Synapse Serverless                             | Implemented and validated                |
| Power BI serving                               | Implemented                              |
| Databricks Free Edition ML                     | Implemented and validated                |
| XGBoost classification                         | Implemented and evaluated                |
| Isolation Forest                               | Implemented and evaluated                |
| SHAP explainability                            | Implemented                              |
| MLflow experiment/model tracking               | Implemented within project scope         |
| Databricks → ADLS handoff                      | Implemented as controlled manual handoff |
| GitHub Actions CI                              | Implemented                              |
| GitHub Actions controlled CD validation        | Implemented                              |
| Security/governance documentation              | Implemented                              |
| Terraform foundation                           | Implemented                              |
| Full Terraform recreation of Azure environment | Not implemented                          |
| Enterprise production controls                 | Outside current scope                    |

---

# 18. Architecture Evolution

The project evolved from a simple Azure foundation into a multi-layer analytical platform.

The progression was:

```text
Day 0
Azure foundation
      │
      ▼
ADLS + Event Hubs
      │
      ▼
Day 1–4
ADF + CDC streaming
      │
      ▼
Day 5
Medallion transformations
      │
      ▼
Day 6
Databricks ML
      │
      ▼
Day 7
Synapse + Power BI serving
      │
      ▼
Day 8
CI/CD + data quality
+ security/governance
+ architecture decisions
+ Terraform foundation
```

This evolution reflects incremental engineering rather than attempting to provision every component before validating the preceding layer.

---

# 19. Related Documentation

Key supporting documents include:

```text
docs/
├── architecture.md
├── architecture-decisions.md
├── databricks-integration.md
├── data-contract.md
├── data-sources.md
├── day4-cdc-streaming.md
├── day7-power-bi-serving.md
├── security-governance.md
└── adr/
    └── ADR-005-databricks-free-edition-integration.md
```

The architecture overview describes the overall platform.

Architecture decisions document why major design choices were made.

Individual ADRs provide formal records for significant architectural decisions.

Implementation-specific documentation provides deeper details for individual components.

---

# 20. Summary

The final architecture separates Azure ingestion and orchestration from Databricks ML execution while maintaining ADLS Gen2 as the common logical data boundary.

The core Azure path is:

```text
External Sources
      │
      ├───────────────┐
      ▼               ▼
     ADF          Event Hubs
      │               │
      ▼               ▼
  ADLS RAW       Python Consumer
      │               │
      └───────┬───────┘
              ▼
           Bronze
              │
              ▼
           Silver
              │
              ▼
            Gold
              │
       ┌──────┴──────┐
       ▼             ▼
    Synapse       ML-ready
       │             │
       ▼             ▼
   Power BI      Databricks
                    Free Edition
                       │
                       ▼
                  ML Outputs
                       │
                controlled handoff
                       │
                       ▼
                    ADLS ML
                       │
                       ▼
                  Synapse
                       │
                       ▼
                   Power BI
```

The architecture prioritizes clear ownership of responsibilities, reproducibility, data quality, identity-based access, explicit platform constraints, and cost awareness.

It documents the system as actually implemented rather than presenting planned or unavailable capabilities as completed functionality.
