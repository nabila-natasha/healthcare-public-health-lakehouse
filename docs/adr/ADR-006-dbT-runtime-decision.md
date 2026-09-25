# ADR-006: dbt Runtime Decision

**Status:** Accepted  
**Date:** 18 September 2026  
**Decision Type:** Platform / Tooling Constraint & Architecture 

## Context

The project evaluated dbt as a SQL transformation and analytics-engineering layer.

The selected Azure architecture uses **Azure Synapse Serverless SQL** to query data stored in Azure Data Lake Storage Gen2 (ADLS Gen2). No Synapse Dedicated SQL Pool is planned because the project does not require a persistent dedicated SQL warehouse for its current workload.

The official `dbt-synapse` adapter targets Azure Synapse Dedicated SQL Pools. Using dbt as the runtime transformation engine would therefore introduce an architectural mismatch with the selected Synapse Serverless design.

Creating a Dedicated SQL Pool solely to accommodate dbt would add an additional Azure resource and cost without providing a requirement-driven benefit to the project.

```text
dbt Core installed
       ↓
Adapter initially unavailable
       ↓
Investigated
       ↓
dbt-synapse discovered/installed
       ↓
Adapter available
       ↓
Checked architecture
       ↓
dbt-synapse → Dedicated SQL Pool
       ↓
Our architecture → Serverless SQL
       ↓
Don't create Dedicated SQL Pool
       ↓
DROP dbt from core runtime
```

## Decision

dbt will **not be used as a runtime transformation engine** in the core project architecture.

The project will retain:

* Azure Event Hubs with Kafka protocol for streaming ingestion
* ADLS Gen2 for lake storage
* Databricks for lakehouse processing and transformation
* Synapse Serverless SQL for SQL-based validation and ad-hoc querying
* Power BI for analytics and visualization
* GitHub Actions for CI/CD

No Synapse Dedicated SQL Pool will be created solely to support dbt.

## Alternatives Considered

### 1. Use dbt with Synapse Dedicated SQL Pool

This provides a supported dbt/Synapse runtime combination, but would require introducing a Dedicated SQL Pool that is not otherwise required by the project.

**Decision:** Not selected because it adds unnecessary infrastructure and cost.

### 2. Use an experimental Serverless-oriented dbt adapter

A Serverless-oriented adapter exists as an experimental approach, but relying on an experimental adapter would introduce unnecessary runtime risk into a time-boxed portfolio project.

**Decision:** Not selected.

### 3. Use dbt only as a development/CI validation tool

dbt could be retained for SQL modelling, parsing, testing, documentation, or CI validation without making it a production runtime dependency.

**Decision:** Not required for the core project. The project will prioritize the Databricks transformation path and may demonstrate dbt separately only if it provides clear portfolio value without complicating the architecture.

## Consequences

### Positive

* The architecture remains aligned with the project's actual requirements.
* No Dedicated SQL Pool is required.
* Azure trial resources and time are not spent supporting an unnecessary component.
* Databricks remains the primary lakehouse transformation engine.
* Synapse Serverless remains useful as a SQL query and validation layer.
* The decision demonstrates technology evaluation rather than adding tools solely for technology breadth.

### Negative

* The project does not demonstrate dbt as a production transformation runtime.
* dbt-specific modelling and testing features are not part of the core execution path.
* A future version of the project could revisit dbt if a compatible runtime architecture is introduced.

## Revisit Conditions

Reconsider dbt if the architecture later requires:

* Synapse Dedicated SQL Pool,
* a supported dbt adapter for the selected Serverless/lakehouse execution environment,
* or a separate analytics warehouse where dbt provides a clear operational benefit.

## Result

Gate 7 — dbt evaluation: **Completed**

Outcome: **Not selected for core runtime architecture.**

The project proceeds with Databricks as the primary transformation engine and Synapse Serverless SQL as a query/validation layer.

