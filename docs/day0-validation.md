# Azure Day 0 Validation

**Date:** 18 September 2026  
**Project:** Healthcare Public Health Surveillance & Risk Analytics Lakehouse

## Account

- Azure Free Account: PASS
- Subscription name: [record privately]
- Subscription ID: [DO NOT COMMIT]
- Tenant ID: [DO NOT COMMIT]
- Trial start date: [private]
- Trial end date: [private]
- Starting credit: [private]

## Gates

| Gate | Result |
|---|---|
| 1. Azure account | PASS |
| 2. Cloud Shell | PASS |
| 3. Resource group | PASS |
| 4. ADLS Gen2 | PASS |
| 5. Event Hubs Kafka | PASS - Validated Kafka-compatible streaming connectivity between a Python producer, Azure Event Hubs, and a Kafka consumer using the Event Hubs Kafka endpoint and SASL/SSL authentication. |
| 6. Synapse Serverless | PASS |
| 7. dbt | PASS |
| 8. Power BI | NOT TESTED |
| 9. Databricks Free Edition | NOT TESTED |

## Architecture decisions

- Storage format:
- Streaming protocol:
- Synapse serving approach:
- dbt decision:

## Issues encountered

## Resolutions

### Gate 7 — dbt Evaluation

**Date:** 2026-09-18  
**Status:** PASS — Evaluation completed; dbt not selected for core runtime

### 1. Objective

Evaluate whether dbt can be used as a runtime SQL transformation layer with the selected Synapse Serverless SQL architecture.

### 2. Environment
- dbt Core: 1.12.5
- dbt-synapse: 1.8.5
- dbt-fabric: 1.9.10
- Azure Synapse workspace: syn-lakehouse-bello
- SQL execution layer selected for the project: Synapse Serverless SQL

### 3. Validation Performed

dbt installation and adapter availability were checked using:

`dbt --version`

Result:

Core:
  installed: 1.12.5

Plugins:
  fabric:  1.9.10
  synapse: 1.8.5

The dbt configuration directory was also successfully located using:

`dbt debug --config-dir`

Result:

/home/bello/.dbt

### 4. Finding

The installed dbt-synapse adapter is intended for Azure Synapse Dedicated SQL Pools.

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

**PASS** — dbt evaluation completed.

The result is an intentional architectural decision, not a failed installation.

Reference:

`docs/adr/ADR-006-dbT-runtime-decision.md`

### Interview Talking Point

> "I evaluated dbt against the selected Synapse architecture. The official Synapse adapter targets Dedicated SQL Pools, while my architecture deliberately uses Serverless SQL to query ADLS without introducing a dedicated warehouse. Rather than add infrastructure solely to accommodate dbt, I kept Databricks as the primary transformation engine and documented the trade-off in an ADR."


## Evidence
