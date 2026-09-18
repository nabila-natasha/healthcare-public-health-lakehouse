# Azure Day 0 Validation

**Date:** 18 September 2026
**Project:** Healthcare Public Health Surveillance & Risk Analytics Lakehouse

## Account

* Azure Free Account: PASS
* Subscription name: [record privately]
* Subscription ID: [DO NOT COMMIT]
* Tenant ID: [DO NOT COMMIT]
* Trial start date: [private]
* Trial end date: [private]
* Starting credit: [private]

---

## Gates

| Gate                       | Result                                                                                                                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Azure account           | PASS                                                                                                                                                                                         |
| 2. Cloud Shell             | PASS                                                                                                                                                                                         |
| 3. Resource group          | PASS                                                                                                                                                                                         |
| 4. ADLS Gen2               | PASS                                                                                                                                                                                         |
| 5. Event Hubs Kafka        | PASS — Validated Kafka-compatible streaming connectivity between a Python producer, Azure Event Hubs, and a Kafka consumer using the Event Hubs Kafka endpoint with SASL/SSL authentication. |
| 6. Synapse Serverless      | PASS — Validated Serverless SQL access to the project ADLS Gen2 account using an explicit ADLS path.                                                                                         |
| 7. dbt                     | PASS — Evaluation completed; dbt not selected for the core runtime.                                                                                                                          |
| 8. Power BI                | PASS — Synapse Serverless connection and authentication validated.                                                                                                                           |
| 9. Databricks Free Edition | PASS                                                                                                                                                                                         |

---

# Architecture Decisions

### Storage

**Decision:** Azure Data Lake Storage Gen2 with hierarchical namespace.

Primary project storage:

```text
stlakehousebello
└── healthcare/
    ├── raw/
    ├── bronze/
    ├── silver/
    └── gold/
```

The project will use `stlakehousebello/healthcare` as the primary data lake.

The older storage account `stlakehouse123` remains temporarily because the Synapse workspace was originally created with it as its immutable default data lake storage reference. It is not used as the primary project data lake.

### Storage Format

**Decision:** Parquet for persisted analytical/lakehouse data.

Event payloads may initially arrive as JSON through Event Hubs, but the lakehouse layers will use an analytical columnar format where appropriate.

### Streaming Protocol

**Decision:** Kafka-compatible protocol through Azure Event Hubs.

Validated flow:

```text
Python Producer
      ↓
Azure Event Hubs
      ↓
Kafka Consumer
```

Event Hubs namespace:

```text
eh-lakehouse-bello
```

Event Hub:

```text
healthcare-events
```

### Synapse Serving Approach

**Decision:** Synapse Serverless SQL.

Synapse Serverless SQL will be used as a SQL query and validation layer over ADLS rather than as the primary transformation engine.

No Dedicated SQL Pool will be created solely for this project.

### Transformation Engine

**Decision:** Databricks will be the primary transformation engine.

The planned lakehouse flow is:

```text
Event Hubs / Kafka
        ↓
ADLS Gen2
        ↓
Databricks
        ↓
Bronze → Silver → Gold
        ↓
Power BI
```

### dbt Decision

**Decision:** dbt is not included as a core runtime dependency.

dbt was evaluated against the selected Synapse architecture. The installed `dbt-synapse` adapter targets Synapse Dedicated SQL Pools, while this project intentionally uses Synapse Serverless SQL.

Creating a Dedicated SQL Pool solely to accommodate dbt would introduce additional infrastructure and cost without being required by the project's core objectives.

Databricks therefore remains the primary transformation engine.

---

# Issues Encountered

### 1. Synapse default storage could not be changed

The Synapse workspace was originally created with:

```text
stlakehouse123
```

as its default data lake storage.

An attempt was made to change the Synapse `defaultDataLakeStorage` configuration to:

```text
stlakehousebello
```

Azure rejected the update with:

```text
DefaultDataLakeStorageCannotBeUpdated
```

The update did not change the workspace configuration.

### 2. Initial ADLS validation used the old storage account

The initial Synapse Serverless smoke test used:

```text
stlakehouse123 / day0-test / test.parquet
```

This successfully demonstrated Synapse Serverless functionality, but the project architecture was subsequently cleaned up so that `stlakehousebello/healthcare` is the primary project data lake.

### 3. Event Hubs initially used temporary test resources

The initial Kafka smoke test used:

```text
eh-lakehouse-bello / healthcare-events-test
```

The temporary Event Hub was subsequently removed.

The final Event Hub is:

```text
eh-lakehouse-bello / healthcare-events
```

A temporary namespace authorization rule named:

```text
day0-kafka-plicy
```

was also identified as an old Day 0 test artifact and is scheduled for removal during final Day 0 cleanup.

---

# Resolutions

## Gate 4 — ADLS Gen2

A clean project storage account was created:

```text
stlakehousebello
```

with hierarchical namespace enabled.

The project filesystem and layer directories were created:

```text
healthcare/
├── raw/
├── bronze/
├── silver/
└── gold/
```

The Synapse managed identity was granted:

```text
Storage Blob Data Contributor
```

on the new storage account.

Synapse Serverless was then explicitly tested against the new ADLS account.

Validation path:

```text
https://stlakehousebello.dfs.core.windows.net/healthcare/raw/_day0_validation/test.csv
```

The query successfully returned:

```text
1 | synapse-adls-test
2 | access-confirmed
```

**Result: PASS**

The temporary `_day0_validation` directory is not part of the project architecture and should be removed during final cleanup.

---

## Gate 5 — Event Hubs Kafka

The final streaming resource is:

```text
Namespace:
eh-lakehouse-bello

Event Hub:
healthcare-events
```

Kafka-compatible connectivity was validated using a Python producer and consumer.

The producer successfully sent a test event and the consumer successfully received it.

Example validation event:

```json
{
  "event_id": "day0-001",
  "event_type": "healthcare_test",
  "message": "hello-healthcare"
}
```

**Result: PASS**

The final application authorization rule is:

```text
healthcare-app-policy
```

with Send and Listen permissions.

The Azure-managed:

```text
RootManageSharedAccessKey
```

rule is retained.

The obsolete Day 0 test authorization rule:

```text
day0-kafka-plicy
```

should be removed during final cleanup.

---

## Gate 6 — Synapse Serverless

Synapse Serverless SQL was validated against the new project ADLS account using `OPENROWSET`.

Validation flow:

```text
Synapse Serverless SQL
        ↓
stlakehousebello
        ↓
healthcare/raw/
        ↓
CSV test file
        ↓
Rows returned successfully
```

**Result: PASS**

The Serverless endpoint is:

```text
syn-lakehouse-bello-ondemand.sql.azuresynapse.net
```

Synapse Serverless will remain a SQL query/validation layer rather than the primary transformation engine.

---

## Gate 7 — dbt Evaluation

**Date:** 2026-09-18
**Status:** PASS — Evaluation completed; dbt not selected for core runtime

### 1. Objective

Evaluate whether dbt can be used as a runtime SQL transformation layer with the selected Synapse Serverless SQL architecture.

### 2. Environment

* dbt Core: 1.12.5
* dbt-synapse: 1.8.5
* dbt-fabric: 1.9.10
* Azure Synapse workspace: `syn-lakehouse-bello`
* SQL execution layer selected for the project: Synapse Serverless SQL

### 3. Validation Performed

dbt installation and adapter availability were checked using:

```bash
dbt --version
```

Result:

```text
Core:
  installed: 1.12.5

Plugins:
  fabric:  1.9.10
  synapse: 1.8.5
```

The dbt configuration directory was also successfully located using:

```bash
dbt debug --config-dir
```

Result:

```text
/home/bello/.dbt
```

### 4. Finding

The installed `dbt-synapse` adapter is intended for Azure Synapse Dedicated SQL Pools.

The project architecture intentionally uses Synapse Serverless SQL and does not require a Dedicated SQL Pool.

Therefore, using dbt as the core runtime transformation engine would require an architectural change that is not justified by the project's requirements.

### 5. Decision

dbt is not included as a core runtime dependency.

The project will use:

```text
Event Hubs / Kafka
        ↓
ADLS Gen2
        ↓
Databricks
        ↓
Bronze → Silver → Gold
        ↓
Power BI
```

Synapse Serverless SQL will remain available for SQL-based querying and validation over ADLS.

A Synapse Dedicated SQL Pool will not be created solely to support dbt.

### 6. Gate Result

**PASS — Evaluation completed and architectural decision documented.**

The result is an intentional architectural decision, not a failed installation.

Reference:

```text
docs/adr/ADR-006-dbT-runtime-decision.md
```

### Interview Talking Point

> "I evaluated dbt against the selected Synapse architecture. The Synapse adapter targets Dedicated SQL Pools, while my architecture deliberately uses Serverless SQL to query ADLS without introducing a dedicated warehouse. Rather than add infrastructure solely to accommodate dbt, I kept Databricks as the primary transformation engine and documented the trade-off in an ADR."

---

## Gate 8 — Power BI

Power BI successfully connected to the Synapse Serverless SQL endpoint:

```text
syn-lakehouse-bello-ondemand.sql.azuresynapse.net
```

Connection and authentication were accepted.

**Result: PASS — connectivity validated.**

At Day 0, this does **not** represent a completed Power BI dashboard.

The analytical tables/views required for the final dashboard will be created later as part of the Databricks/Synapse/Power BI implementation.

---

## Gate 9 — Databricks Free Edition

Databricks Free Edition was validated as the planned transformation and analytics environment.

**Result: PASS**

Databricks will be used for the primary Bronze → Silver → Gold transformation workflow and later ML/analytics work.

---

# Day 0 Validation Evidence

### ADLS Gen2

Final project storage:

```text
stlakehousebello
└── healthcare/
    ├── raw/
    ├── bronze/
    ├── silver/
    └── gold/
```

Validation:

```text
Synapse Serverless
        ↓
stlakehousebello/healthcare/raw/
        ↓
OPENROWSET
        ↓
PASS
```

### Event Hubs

Final streaming resource:

```text
eh-lakehouse-bello / healthcare-events
        ↓
Kafka producer
        ↓
Azure Event Hubs
        ↓
Kafka consumer
        ↓
PASS
```

### Synapse Serverless

```text
syn-lakehouse-bello-ondemand.sql.azuresynapse.net
        ↓
Explicit ADLS path
        ↓
CSV rows returned
        ↓
PASS
```

### Power BI

```text
Power BI
    ↓
Synapse Serverless endpoint
    ↓
Connection/authentication accepted
    ↓
PASS
```

### dbt

```text
dbt Core + adapters
        ↓
Evaluation
        ↓
Synapse Serverless compatibility assessed
        ↓
Not selected as core runtime
        ↓
PASS — architectural decision
```

---

# Day 0 Final Architecture

```text
                    ┌─────────────────────┐
                    │   Event Generator   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Azure Event Hubs  │
                    │   Kafka-compatible  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      ADLS Gen2      │
                    │ stlakehousebello    │
                    │    /healthcare      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      Databricks     │
                    │ Primary Transformation│
                    └──────────┬──────────┘
                               │
                         Bronze → Silver
                               → Gold
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
          ┌─────────────────┐   ┌─────────────────┐
          │ Synapse         │   │    Power BI     │
          │ Serverless SQL  │   │ Analytics / BI  │
          │ Query/Validation│   │                 │
          └─────────────────┘   └─────────────────┘
```

## Day 0 Status

**Foundation validated and ready for Day 1 implementation.**

Day 0 established:

* Azure resource group
* ADLS Gen2 project storage
* Event Hubs Kafka connectivity
* Synapse Serverless connectivity
* Power BI connectivity
* Databricks Free Edition
* dbt architectural evaluation
* Initial security/RBAC configuration
* Final project architecture

Remaining cleanup items:

* Remove the temporary ADLS `_day0_validation` folder.
* Remove the obsolete Event Hubs `day0-kafka-plicy` authorization rule.
* Refresh the Event Hubs application connection string after the obsolete policy is removed.
* Perform the Terraform smoke test.
* Record final cleanup evidence.

No project transformation pipeline or production dashboard is claimed as complete at Day 0.
