# Architecture Decisions

## 1. Purpose

This document provides a consolidated view of the major architectural decisions made for the Healthcare Public Health Surveillance & Risk Analytics Lakehouse.

It complements:

```text
docs/architecture.md
```

which describes the implemented platform architecture.

Detailed architectural decisions are recorded in:

```text
docs/adr/
```

The purpose of this document is to make the overall design rationale easy to understand without requiring every ADR to be read individually.

---

## 2. Decision Summary

| ID      | Decision                                                           | Status   | Detailed ADR                                     |
| ------- | ------------------------------------------------------------------ | -------- | ------------------------------------------------ |
| ADR-001 | Use ADLS Gen2 as the canonical data-lake storage layer             | Accepted | `ADR-001-adls.md`                                |
| ADR-002 | Use Azure Event Hubs with Kafka-compatible ingestion for streaming | Accepted | `ADR-002-event-hubs.md`                          |
| ADR-003 | Separate batch and streaming ingestion patterns                    | Accepted | `ADR-003-batch-vs-streaming.md`                  |
| ADR-004 | Replay historical CDC data instead of claiming a live CDC source   | Accepted | `ADR-004-replay-vs-live-api.md`                  |
| ADR-005 | Use Databricks Free Edition as a separate ML execution environment | Accepted | `ADR-005-databricks-free-edition-integration.md` |
| ADR-006 | Do not include dbt in the core runtime                             | Accepted | `ADR-006-dbT-runtime-decision.md`                |
| ADR-007 | Use ADF for parameterized openFDA batch ingestion                  | Accepted | `ADR-007-openfda-batch-ingestion.md`             |

---

# 3. ADR-001 — ADLS Gen2 as Canonical Storage

### Decision

Use Azure Data Lake Storage Gen2 as the canonical storage layer for the project.

The lake is organized into logical data layers:

```text
healthcare/
├── raw/
├── bronze/
├── silver/
├── gold/
├── quarantine/
└── ml/
```

### Rationale

ADLS Gen2 provides a suitable cloud storage boundary for both batch and streaming workloads while supporting hierarchical organization and downstream analytical access.

Using a common storage layer also allows the ingestion, transformation, ML, and serving components to remain loosely coupled.

### Alternatives Considered

* Direct database-centric storage
* Separate storage systems for batch and streaming
* Using Synapse as the primary storage layer

These alternatives were not selected because the project benefits from maintaining a centralized lake storage boundary.

### Consequence

ADLS becomes the common logical data boundary between:

```text
ADF
 │
 ├── Batch data
 │
 ▼
ADLS

Event Hubs
 │
 ▼
Python Consumer
 │
 ▼
ADLS

Databricks
 │
 ▼
ML outputs
 │
 ▼
ADLS
```

Detailed rationale is recorded in:

```text
docs/adr/ADR-001-adls.md
```

---

# 4. ADR-002 — Event Hubs for Streaming Ingestion

### Decision

Use Azure Event Hubs as the streaming ingestion endpoint and use its Kafka-compatible interface for the project workload.

### Rationale

The project requires a reproducible streaming ingestion path while remaining within the Azure platform.

Event Hubs provides:

* Partitioned event ingestion
* Consumer groups
* Kafka-compatible connectivity
* Retention-based event storage
* Integration with Azure services

The Kafka interface also demonstrates transferable streaming concepts without requiring a separate Kafka cluster.

### Consequence

The streaming path is:

```text
Historical CDC fixture
        │
        ▼
Python producer
        │
        ▼
Event Hubs
Kafka protocol
        │
        ▼
Python consumer
        │
        ▼
ADLS
```

The Event Hubs namespace uses four partitions and seven-day retention for the current project environment.

Detailed rationale is recorded in:

```text
docs/adr/ADR-002-event-hubs.md
```

---

# 5. ADR-003 — Separate Batch and Streaming Patterns

### Decision

Treat batch ingestion and streaming ingestion as separate workload patterns rather than forcing one technology to handle both.

### Batch

The openFDA workload uses:

```text
openFDA API
     │
     ▼
ADF
     │
     ▼
ADLS
```

### Streaming

The CDC workload uses:

```text
CDC historical replay
        │
        ▼
Event Hubs
        │
        ▼
Python consumer
        │
        ▼
ADLS
```

### Rationale

The workloads have different operational characteristics.

Batch ingestion requires:

* API pagination
* Scheduled execution
* Retry and dependency management
* Controlled data movement

Streaming ingestion requires:

* Event delivery
* Partitioning
* Consumer groups
* Event-time and ingestion-time handling
* Duplicate and malformed-event handling

Keeping the patterns separate makes the architecture easier to reason about and validate.

Detailed rationale is recorded in:

```text
docs/adr/ADR-003-batch-vs-streaming.md
```

---

# 6. ADR-004 — Historical Replay Instead of Live CDC

### Decision

Use archived historical CDC/public-health data replayed at an accelerated cadence to simulate near-real-time event arrival.

The project does not represent the CDC source as a genuine real-time production feed.

### Rationale

A reproducible historical fixture provides:

* Deterministic test data
* Repeatable pipeline execution
* Controlled fault injection
* Safe development without production healthcare data
* Ability to demonstrate event-time versus ingestion-time behavior

The workload also allows controlled duplicate and malformed-event scenarios to be tested.

### Consequence

The streaming workload should be described as:

> Historical public-health surveillance data replayed at an accelerated cadence to simulate near-real-time event arrival, with event-time and ingestion-time preserved and synthetic faults injected.

This wording should be used consistently across project documentation.

Detailed rationale is recorded in:

```text
docs/adr/ADR-004-replay-vs-live-api.md
```

---

# 7. ADR-005 — Databricks Free Edition Integration Boundary

### Decision

Use Databricks Free Edition as a separate ML/PySpark execution environment rather than making the core Azure ingestion architecture dependent on direct Free Edition connectivity.

### Rationale

The selected Free Edition environment does not provide the same Azure storage connectivity and configuration model available in a provisioned Azure Databricks environment.

The project therefore maintains the following boundary:

```text
Azure ingestion
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
ML outputs
       │
       │ controlled handoff
       ▼
ADLS ML layer
```

This allows the project to demonstrate both Azure data engineering and Databricks ML without introducing an additional paid Azure Databricks environment.

### Consequence

The project does not claim fully automated direct Databricks Free Edition → ADLS integration.

The controlled manual handoff is documented as a platform workaround rather than a desired production pattern.

Detailed implementation is documented in:

```text
docs/databricks-integration.md
```

Detailed architectural rationale is recorded in:

```text
docs/adr/ADR-005-databricks-free-edition-integration.md
```

---

# 8. ADR-006 — dbt Not Included in Core Runtime

### Decision

dbt is not part of the core transformation runtime for this project.

### Rationale

The primary transformation implementation already uses Python, Pandas, and PyArrow.

The project uses these tools to implement:

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

Introducing dbt solely to demonstrate another technology would add an additional transformation framework without a corresponding architectural requirement.

The decision therefore prioritizes:

* Clear ownership of transformation logic
* Reduced runtime complexity
* Consistency with the implemented codebase
* Avoiding unnecessary technology duplication

### Consequence

dbt remains a considered technology but is not represented as an implemented runtime dependency.

If the platform later adopts a warehouse-centric transformation architecture, dbt could be reconsidered.

Detailed rationale is recorded in:

```text
docs/adr/ADR-006-dbT-runtime-decision.md
```

---

# 9. ADR-007 — ADF for openFDA Batch Ingestion

### Decision

Use Azure Data Factory for parameterized batch ingestion of the openFDA REST API.

### Rationale

ADF provides appropriate orchestration capabilities for the batch workload, including:

* REST/HTTP connectivity
* Parameterized requests
* Pagination
* Scheduling
* Pipeline execution monitoring
* Azure-native orchestration

The project uses API pagination rather than assuming a single request can retrieve the required dataset.

The implemented ingestion was validated using multiple API pages.

### Consequence

The batch path is:

```text
openFDA API
     │
     ▼
ADF REST / HTTP
     │
     ▼
ADLS RAW
```

The ADF pipeline remains separate from the Event Hubs streaming path.

Detailed rationale is recorded in:

```text
docs/adr/ADR-007-openfda-batch-ingestion.md
```

---

# 10. Cross-Cutting Implementation Decisions

The following decisions are important to the final architecture but do not currently require separate ADRs.

---

## 10.1 Parquet for Analytical Layers

### Decision

Use Parquet for Silver, Gold, and ML analytical datasets.

### Rationale

Parquet provides:

* Typed columns
* Columnar storage
* Compression
* Efficient analytical reads
* Compatibility with Python, Spark, Synapse, and BI workflows

This provides a consistent file format across the analytical layers.

### Consequence

The primary analytical path is:

```text
Bronze
  │
  ▼
Parquet Silver
  │
  ▼
Parquet Gold
  │
  ▼
Synapse Serverless
```

ML outputs also use Parquet.

---

## 10.2 Synapse Serverless Instead of Dedicated SQL Pool

### Decision

Use Synapse Serverless SQL rather than provisioning a Dedicated SQL Pool.

### Rationale

The project requires SQL-based serving and validation rather than a continuously running data warehouse.

Serverless SQL provides an appropriate serving layer over ADLS while avoiding the cost and operational overhead of a Dedicated SQL Pool.

### Consequence

The serving pattern is:

```text
ADLS
  │
  ▼
Synapse Serverless
  │
  ▼
Power BI
```

A Dedicated SQL Pool is outside the current project scope.

---

## 10.3 Python Consumer for Event Hubs to ADLS

### Decision

Use a Python Kafka consumer to consume Event Hubs events and persist validated events to ADLS.

### Rationale

The consumer provides explicit control over:

* Event envelope validation
* Required-field validation
* Duplicate detection
* Quarantine
* Event-time and ingestion-time handling
* ADLS persistence

This also makes the streaming behavior transparent and reproducible for the portfolio project.

### Consequence

The streaming persistence path is:

```text
Event Hubs
    │
    ▼
Python consumer
    │
    ├── Valid → Bronze
    │
    └── Invalid → Quarantine
```

---

## 10.4 Public and Synthetic Data

### Decision

Use public openFDA data and synthetic/historical public-health data rather than PHI or patient-identifiable clinical records.

### Rationale

The project is intended to demonstrate healthcare/public-health data engineering without creating unnecessary privacy and compliance risks.

The data is therefore suitable for portfolio development and reproducible testing.

### Consequence

The project does not claim to implement a production clinical data platform.

The ML outputs are analytical signals rather than clinical decisions.

---

## 10.5 Terraform as an Infrastructure Foundation

### Decision

Use Terraform as an infrastructure-as-code foundation without recreating or destroying the existing Azure environment solely for the purpose of Terraform adoption.

### Rationale

The Azure environment was provisioned incrementally during development.

Recreating the environment would introduce unnecessary risk and could create avoidable cost or configuration changes.

Terraform therefore establishes a path toward reproducible infrastructure management without pretending that the current environment is already fully Terraform-managed.

### Consequence

The current implementation demonstrates:

* AzureRM provider initialization
* Terraform project structure
* Variables and outputs
* A path toward selective resource import

It does not claim full Terraform management of the existing Azure subscription.

---

## 10.6 CI/CD Separation from Infrastructure Deployment

### Decision

Use GitHub Actions for repository validation and controlled release validation, while keeping Azure infrastructure provisioning separate.

### Rationale

The project has two different concerns:

```text
Application / Data Code
        │
        ▼
GitHub Actions
        │
        ├── Compilation
        ├── Tests
        └── Release validation
```

and:

```text
Infrastructure
        │
        ▼
Terraform / Azure
```

Separating them avoids implying that the current CI/CD workflow automatically manages the entire Azure environment.

### Consequence

CI validates changes automatically.

CD performs controlled release validation.

The current CD workflow does not automatically recreate or destroy Azure resources.

---

# 11. Decision Principles

The architecture decisions follow several common principles.

## Avoid Unnecessary Complexity

A technology is included because it provides a meaningful architectural capability, not simply because it appears in a typical cloud stack.

## Prefer Explicit Trade-offs

Where a platform limitation exists, the project documents the limitation rather than hiding it.

## Preserve Reproducibility

Historical replay, deterministic event IDs, controlled fixtures, and automated tests allow the pipeline to be repeatedly validated.

## Separate Concerns

Ingestion, orchestration, storage, transformation, ML, serving, and visualization have separate responsibilities.

## Design for Evolution

The current implementation is intentionally cost-conscious while documenting how it could evolve toward a provisioned production environment.

## Do Not Overstate Production Readiness

The project distinguishes between:

* Implemented functionality
* Validated functionality
* Platform workarounds
* Production-evolution opportunities

---

# 12. Architecture Decision Relationship

The relationship between the documentation layers is:

```text
                         architecture.md
                               │
                     Overall platform design
                               │
                               ▼
                  architecture-decisions.md
                               │
                  Consolidated decision summary
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
          ADR-001           ADR-002           ADR-003
             │                 │                 │
             ▼                 ▼                 ▼
          ADR-004           ADR-005           ADR-006
                               │
                               ▼
                           ADR-007
```

The individual ADRs remain the authoritative records for their respective decisions.

This document provides the consolidated view.

---

# 13. Current Decision Status

| Area                        | Current Decision                     |
| --------------------------- | ------------------------------------ |
| Lake storage                | ADLS Gen2                            |
| Batch ingestion             | Azure Data Factory                   |
| Streaming ingestion         | Azure Event Hubs with Kafka protocol |
| Streaming source            | Historical CDC replay                |
| Streaming persistence       | Python consumer → ADLS               |
| Data architecture           | Raw → Bronze → Silver → Gold         |
| Invalid records             | Quarantine                           |
| Analytical file format      | Parquet                              |
| Transformation runtime      | Python / Pandas / PyArrow            |
| SQL serving                 | Synapse Serverless                   |
| BI                          | Power BI Desktop                     |
| ML execution                | Databricks Free Edition              |
| Databricks storage boundary | Managed Unity Catalog volume         |
| Databricks → ADLS           | Controlled manual handoff            |
| ML methods                  | XGBoost, Isolation Forest, SHAP      |
| Experiment tracking         | MLflow within project scope          |
| Infrastructure-as-code      | Terraform foundation                 |
| CI/CD                       | GitHub Actions                       |
| dbt                         | Considered, not part of core runtime |
| Data classification         | Public and synthetic                 |
| PHI                         | Not used                             |

---

# 14. Future Architecture Evolution

The decisions documented here are specific to the current portfolio implementation.

A production implementation could evolve toward:

```text
External Sources
       │
       ├───────────────┐
       ▼               ▼
      ADF          Event Hubs
       │               │
       └───────┬───────┘
               ▼
             ADLS
               │
        Bronze / Silver
               │
               ▼
      Azure Databricks
               │
       ┌───────┴────────┐
       ▼                ▼
      ML              Gold
       │                │
       └───────┬────────┘
               ▼
       Synapse / SQL
               │
               ▼
            Power BI
```

Potential production evolution includes:

* Provisioned Azure Databricks
* Automated ADLS integration
* Managed identities and external locations
* Automated ML pipelines
* Enterprise model governance
* Production monitoring
* Private networking
* Key Vault integration
* Data cataloguing and lineage
* More comprehensive infrastructure-as-code management

These are future capabilities and are not represented as currently implemented.

---

# 15. Summary

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

The overall design prioritizes explicit responsibilities, reproducibility, data quality, security, cost awareness, and transparent documentation of platform constraints.
