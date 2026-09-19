# Healthcare Public Health Surveillance & Risk Analytics Lakehouse

## 1. Architecture Overview

This project implements a healthcare/public-health analytics platform combining batch ingestion, simulated streaming ingestion, cloud data-lake processing, SQL serving, business intelligence, and machine learning.

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

This separation allows each platform component to have a clearly defined responsibility.

---

## 2. High-Level Architecture

```text
                         BUSINESS REQUIREMENTS
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
                    ▼                            ▼
             BATCH INGESTION              STREAM INGESTION
               openFDA API                  CDC fixture
                    │                     replay producer
                    ▼                            │
                   ADF                           ▼
             REST / HTTP                    Event Hubs
                    │                      Kafka protocol
                    ▼                            │
                ADLS RAW                         ▼
                                           Python Consumer
                                                │
                                                ▼
                                           ADLS RAW
                    │                            │
                    └─────────────┬──────────────┘
                                  ▼
                         DATA QUALITY GATE
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
                              │
                              ▼
                         ADLS ML output
                              │
                              ▼
                      Synapse Serverless
                              │
                              ▼
                          Power BI
```

---

## 3. Azure Infrastructure

### Resource Group

```text
rg-lakehouse-portfolio
```

The resource group provides the logical boundary for the project's Azure resources.

### ADLS Gen2

Primary project storage:

```text
stlakehousebello
└── healthcare/
    ├── raw/
    ├── bronze/
    ├── silver/
    ├── gold/
    └── quarantine/
```

The storage layers represent increasing levels of data refinement.

### Event Hubs

```text
Namespace:
eh-lakehouse-bello

Event Hub:
healthcare-events
```

Azure Event Hubs provides the streaming ingestion endpoint using its Kafka-compatible interface.

### Azure Data Factory

```text
adf-lakehouse-bello
```

ADF is the primary cloud orchestration service.

Its responsibilities include:

* batch API ingestion
* pipeline orchestration
* dependency management
* scheduling
* movement of data between processing stages where appropriate
* invoking downstream processing

ADF is not intended to replace Databricks as the transformation compute engine.

### Synapse Serverless

```text
syn-lakehouse-bello
```

Synapse Serverless SQL provides SQL-based access and validation over files stored in ADLS.

A Dedicated SQL Pool is intentionally not used.

---

# 4. Data Ingestion

## 4.1 Batch ingestion

The batch source is the public openFDA API.

Planned flow:

```text
openFDA API
     ↓
ADF REST / HTTP
     ↓
ADLS RAW
```

ADF provides orchestration and repeatability for the batch ingestion process.

The raw layer preserves source data before transformation.

---

## 4.2 Streaming ingestion

The streaming source is a synthetic CDC/public-health event fixture.

The project uses replayed historical records at an accelerated cadence to simulate near-real-time event arrival.

Flow:

```text
CDC fixture
     ↓
Python replay producer
     ↓
Kafka protocol
     ↓
Azure Event Hubs
     ↓
Python Kafka consumer
     ↓
ADLS
```

This approach provides a reproducible streaming workload without requiring a production CDC source.

---

# 5. Data Lake Layers

## Raw

The Raw layer contains data as received from external sources, with minimal modification.

Purpose:

* source preservation
* replayability
* traceability
* ingestion auditing

```text
healthcare/raw/
```

---

## Bronze

Bronze contains validated ingestion outputs prepared for downstream processing.

```text
healthcare/bronze/
```

Streaming events will preserve important metadata including:

```text
event_id
event_time
ingestion_time
source
```

---

## Silver

Silver contains cleaned, standardized and business-ready records.

Typical processing includes:

* schema normalization
* type conversion
* null handling
* duplicate handling
* standardization
* data-quality rules
* derived operational fields

```text
healthcare/silver/
```

---

## Gold

Gold contains curated analytical datasets designed for reporting and downstream ML use.

```text
healthcare/gold/
```

Gold datasets should represent clearly defined business grains and metrics rather than simply being copies of Silver data.

---

## Quarantine

Records failing validation are separated from accepted records.

```text
healthcare/quarantine/
```

This prevents malformed or invalid records from silently entering analytical datasets.

---

# 6. Data Quality

Data quality is treated as a pipeline gate rather than an afterthought.

The streaming path will validate:

* required fields
* event ID presence
* timestamp validity
* schema conformity
* duplicate event IDs
* acceptable event types
* required source metadata

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

Duplicate detection will initially use `event_id` as the business key.

---

# 7. Synapse Serverless

Synapse Serverless SQL is used as the SQL access and validation layer.

It can query files directly from ADLS without requiring a continuously running dedicated warehouse.

Conceptually:

```text
ADLS Gold
    │
    ▼
Synapse Serverless
    │
    ├── SQL validation
    ├── analytical queries
    └── Power BI connectivity
```

The project deliberately avoids a Dedicated SQL Pool.

---

# 8. Power BI

Power BI Desktop provides the business intelligence layer.

The intended flow is:

```text
ADLS Gold
     ↓
Synapse Serverless
     ↓
Power BI Desktop
```

Power BI will eventually present:

* public-health trends
* event volumes
* regional patterns
* data-quality indicators
* operational latency
* risk indicators
* ML predictions where appropriate

A Day 0 connection test does not represent a completed dashboard.

---

# 9. Databricks Free Edition

Databricks Free Edition is used for the machine-learning and PySpark portion of the project.

Planned workloads include:

* PySpark transformations where appropriate
* feature engineering
* baseline model
* XGBoost
* Isolation Forest
* SHAP
* MLflow experiment tracking
* prediction generation

The Databricks environment is deliberately separated from the primary Azure ingestion path.

### Reason

The Free Edition environment does not provide the same external Azure resource connectivity and integration capabilities available in a standard Azure Databricks deployment.

Therefore, the architecture does not make critical ingestion dependent on Databricks Free Edition being able to directly access the Azure lake.

Instead:

```text
Azure ingestion / orchestration
             │
             ▼
           ADLS
             │
             ▼
      ML-ready dataset
             │
             ▼
 Databricks Free Edition
             │
             ▼
       ML predictions
             │
             ▼
           ADLS
```

This boundary is documented in:

```text
docs/adr/ADR-007-databricks-free-edition-integration.md
```

The project does not claim that the Free Edition environment provides the same production integration model as Azure Databricks.

---

# 10. Terraform

Terraform is used as the infrastructure-as-code layer.

Conceptually:

```text
                     Terraform
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
        ADLS         Event Hubs         ADF
          │                             │
          └────────── Synapse ──────────┘
```

Day 0/Day 1 validation established that Terraform and the AzureRM provider can initialize successfully.

The current smoke-test configuration intentionally contains no Azure resource declarations.

Existing resources will not be recreated simply to place them under Terraform.

Where Terraform management provides value, existing resources may be imported selectively and new infrastructure can be provisioned through Terraform.

---

# 11. Service Responsibility Matrix

| Component               | Primary responsibility                   |
| ----------------------- | ---------------------------------------- |
| Azure Event Hubs        | Streaming event ingestion                |
| Python producer         | CDC event replay                         |
| Python consumer         | Kafka consumption and initial validation |
| ADLS Gen2               | Lake storage                             |
| ADF                     | Cloud orchestration and batch ingestion  |
| Databricks Free Edition | PySpark and ML execution                 |
| Synapse Serverless      | SQL query and validation                 |
| Power BI Desktop        | BI and visualization                     |
| Terraform               | Infrastructure provisioning              |
| dbt                     | Not part of core runtime                 |

---

# 12. Key Architecture Principles

### Separation of concerns

Each platform component has a defined responsibility rather than being included simply to increase the number of technologies.

### Reproducibility

The streaming workload uses a synthetic replay source so that the pipeline can be repeatedly tested.

### Data lineage

Raw → Bronze → Silver → Gold provides traceability through the data lifecycle.

### Data quality

Invalid data is quarantined instead of being silently discarded.

### Identity-based access

Azure managed identities and RBAC are preferred over embedding long-lived storage credentials in pipeline configuration.

### Cost awareness

The architecture deliberately avoids:

* AKS
* VMs
* Dedicated Synapse SQL Pool
* unnecessary monitoring stacks
* private networking
* unnecessary Azure Databricks infrastructure

The project is designed around the available Azure trial/free resources.

### Platform-aware design

The architecture explicitly accounts for the limitations of Databricks Free Edition rather than assuming that Free Edition provides the same integration capabilities as a full Azure Databricks deployment.

---

# 13. Current Architecture Status

As of Day 0:

```text
Azure foundation              PASS
ADLS Gen2                     PASS
Event Hubs / Kafka            PASS
Synapse Serverless            PASS
Power BI connectivity         PASS
Databricks Free Edition       PASS
dbt evaluation                PASS
Terraform provider validation PASS
ADF                            NEXT — Day 1
```

Day 1 begins implementation of the orchestration layer.

Day 2 begins the streaming vertical slice.
