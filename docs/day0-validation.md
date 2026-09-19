# Azure Day 0 & Day 1 Validation

**Date:** 18–19 September 2026  
**Project:** Healthcare Public Health Surveillance & Risk Analytics Lakehouse

---

# Account

* Azure Free Account: PASS
* Subscription name: [record privately]
* Subscription ID: [DO NOT COMMIT]
* Tenant ID: [DO NOT COMMIT]
* Trial start date: [private]
* Trial end date: [private]
* Starting credit: [private]

> **Security note:** Subscription IDs, tenant IDs, credentials, connection strings, access keys, and other secrets must not be committed to the repository.

---

# Day 0 Gates

| Gate                       | Result                                                                                                                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Azure account           | PASS                                                                                                                                                                                         |
| 2. Cloud Shell             | PASS                                                                                                                                                                                         |
| 3. Resource group          | PASS                                                                                                                                                                                         |
| 4. ADLS Gen2               | PASS — Project storage account and hierarchical namespace validated.                                                                                                                         |
| 5. Event Hubs Kafka        | PASS — Validated Kafka-compatible streaming connectivity between a Python producer, Azure Event Hubs, and a Kafka consumer using the Event Hubs Kafka endpoint with SASL/SSL authentication. |
| 6. Synapse Serverless      | PASS — Validated Serverless SQL access to the project ADLS Gen2 account using an explicit ADLS path.                                                                                         |
| 7. dbt                     | PASS — Evaluation completed; dbt not selected for the core runtime.                                                                                                                          |
| 8. Power BI                | PASS — Synapse Serverless connection and authentication validated.                                                                                                                           |
| 9. Databricks Free Edition | PASS — Environment validated for the planned PySpark/ML workload.                                                                                                                            |
| 10. Day 0 architecture     | PASS — Architecture and key technology decisions documented.                                                                                                                                 |

---

# Day 0 Architecture Decisions

## Storage

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

The project will use:

```text
stlakehousebello/healthcare
```

as the primary project data lake.

The `quarantine/` directory was subsequently added during Day 1 for invalid or rejected records:

```text
healthcare/
├── raw/
├── bronze/
├── silver/
├── gold/
└── quarantine/
```

The older storage account `stlakehouse123` remains temporarily because the Synapse workspace was initially provisioned with a separate ADLS Gen2 account (`stlakehouse123`) as its immutable default workspace storage. Azure does not permit changing the workspace's defaultDataLakeStorage configuration after creation.

The project therefore uses stlakehousebello/healthcare as its explicit application data lake. Synapse Serverless has been validated against this storage account, and Azure Data Factory has also been validated against it using managed identity and RBAC.

The original Synapse default storage is retained as workspace infrastructure and is not used as the project's application data lake.

---

## Storage Format

**Decision:** Parquet for persisted analytical/lakehouse data.

Event payloads may initially arrive as JSON through Event Hubs, while raw API/file inputs may arrive in their source format. The Bronze, Silver, and Gold lakehouse layers will use an analytical columnar format such as Parquet where appropriate.

---

## Streaming Protocol

**Decision:** Kafka-compatible protocol through Azure Event Hubs.

Validated Day 0 flow:

```text
Python Producer
      ↓
Azure Event Hubs
      ↓
Kafka Consumer
```

Final streaming resources:

```text
Namespace:
eh-lakehouse-bello

Event Hub:
healthcare-events
```

The Event Hub uses four partitions and seven-day message retention.

The Kafka-compatible endpoint was successfully tested using a Python producer and consumer with SASL/SSL authentication.

---

## Batch Ingestion and Orchestration

**Decision:** Azure Data Factory is the cloud orchestration layer for batch ingestion.

ADF will be used to orchestrate scheduled or triggered movement of source data into ADLS.

Initial Day 1 validation flow:

```text
ADF
 ↓
ADLS Gen2
 ↓
healthcare/raw/
```

ADF uses its managed identity to access the storage account through Azure RBAC rather than embedding storage account keys in the pipeline.

---

## Synapse Serving Approach

**Decision:** Synapse Serverless SQL.

Synapse Serverless SQL will be used as a SQL query and validation layer over ADLS rather than as the primary transformation engine.

No Dedicated SQL Pool will be created solely for this project.

---

## Transformation Engine

**Decision:** Databricks Free Edition is the planned PySpark and ML execution environment.

The Azure production-style ingestion path is intentionally kept independent of Databricks Free Edition's external connectivity limitations.

The architectural boundary is therefore:

```text
                    Azure-managed pipeline
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
        Batch ingestion            Stream ingestion
              │                           │
              ▼                           ▼
             ADF                    Event Hubs
              │                           │
              └─────────────┬─────────────┘
                            ▼
                         ADLS Gen2
                            │
                            ▼
                   Data Quality Gate
                            │
                     Bronze → Silver
                            → Gold
                            │
               ┌────────────┴────────────┐
               │                         │
               ▼                         ▼
      Synapse Serverless          ML-ready dataset
      SQL / Validation                   │
                                         ▼
                               Databricks Free Edition
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

This separation avoids making the critical Azure ingestion pipeline dependent on capabilities that are not available in the Databricks Free Edition environment.

Reference:

```text
docs/adr/ADR-005-databricks-free-edition-integration.md
```

---

## dbt Decision

**Decision:** dbt is not included as a core runtime dependency.

dbt was evaluated against the selected Synapse architecture. The installed `dbt-synapse` adapter targets Synapse Dedicated SQL Pools, while this project intentionally uses Synapse Serverless SQL.

Creating a Dedicated SQL Pool solely to accommodate dbt would introduce additional infrastructure and cost without being required by the project's core objectives.

Databricks therefore remains the primary transformation and ML execution environment.

Synapse Serverless remains available for SQL-based querying and validation over ADLS.

Reference:

```text
docs/adr/ADR-006-dbT-runtime-decision.md
```

---

# Day 0 Issues Encountered

## 1. Synapse Default Storage Could Not Be Changed

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

### Resolution

The new project storage account is used explicitly in Synapse SQL queries.

The old storage account remains only because the existing Synapse workspace retains an immutable reference to it.

The project does **not** use the old storage account as its primary data lake.

---

## 2. Initial ADLS Validation Used the Old Storage Account

The initial Synapse Serverless smoke test used:

```text
stlakehouse123 / day0-test / test.parquet
```

This successfully demonstrated Synapse Serverless functionality, but the project architecture was subsequently cleaned up so that:

```text
stlakehousebello/healthcare
```

is the primary project data lake.

A second validation was successfully performed against the new storage account using an explicit ADLS path.

---

## 3. Event Hubs Initially Used Temporary Test Resources

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

was also identified as an old Day 0 test artifact.

It should be removed during cleanup.

---

# Day 0 Gate Evidence

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

The `quarantine/` directory was added during Day 1.

The Synapse managed identity was granted:

```text
Storage Blob Data Contributor
```

on the new storage account.

Synapse Serverless was explicitly tested against the new ADLS account.

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

The temporary `_day0_validation` directory is not part of the project architecture and should be removed during cleanup.

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

should be removed during cleanup.

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

Synapse Serverless will remain a SQL query and validation layer rather than the primary transformation engine.

---

## Gate 7 — dbt Evaluation

**Date:** 2026-09-18
**Status:** PASS — Evaluation completed; dbt not selected for core runtime.

### Objective

Evaluate whether dbt can be used as a runtime SQL transformation layer with the selected Synapse Serverless SQL architecture.

### Environment

* dbt Core: 1.12.5
* dbt-synapse: 1.8.5
* dbt-fabric: 1.9.10
* Azure Synapse workspace: `syn-lakehouse-bello`
* SQL execution layer selected for the project: Synapse Serverless SQL

### Validation Performed

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

### Finding

The installed `dbt-synapse` adapter is intended for Azure Synapse Dedicated SQL Pools.

The project architecture intentionally uses Synapse Serverless SQL and does not require a Dedicated SQL Pool.

Therefore, using dbt as the core runtime transformation engine would require an architectural change that is not justified by the project's requirements.

### Decision

dbt is not included as a core runtime dependency.

The project will use Databricks as the primary transformation and ML execution environment, while Synapse Serverless provides SQL querying and validation over ADLS.

### Gate Result

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

At Day 0, this did **not** represent a completed Power BI dashboard.

The analytical tables/views required for the final dashboard will be created later as part of the Databricks/Synapse/Power BI implementation.

---

## Gate 9 — Databricks Free Edition

Databricks Free Edition was validated as the planned PySpark and ML environment.

**Result: PASS**

The Free Edition environment will be used for:

* PySpark transformation development
* Data quality/analytics experimentation where appropriate
* ML model development
* ML prediction generation

The critical Azure ingestion path does not depend on direct external connectivity from Databricks Free Edition.

Reference:

```text
docs/adr/ADR-005-databricks-free-edition-integration.md
```

---

# Day 1 Implementation

**Date:** 2026-09-19

**Objective:** Establish the core Azure orchestration layer and prove a cloud-managed batch ingestion path from Azure Data Factory into ADLS Gen2.

---

## Day 1 Gate 1 — ADLS Quarantine Layer

A quarantine directory was added to the project filesystem:

```text
stlakehousebello
└── healthcare/
    ├── raw/
    ├── bronze/
    ├── silver/
    ├── gold/
    └── quarantine/
```

Purpose:

```text
Valid records
     ↓
Normal pipeline

Invalid / rejected records
     ↓
Quarantine
```

This creates a clear data-quality boundary for later ingestion and transformation workflows.

**Result: PASS**

---

## Day 1 Gate 2 — Azure Data Factory

Azure Data Factory was created:

```text
adf-lakehouse-bello
```

Resource group:

```text
rg-lakehouse-portfolio
```

Region:

```text
Southeast Asia
```

ADF is the project's batch ingestion and cloud orchestration service.

**Result: PASS**

---

## Day 1 Gate 3 — ADF Managed Identity and RBAC

ADF's system-assigned managed identity was enabled and granted:

```text
Storage Blob Data Contributor
```

on:

```text
stlakehousebello
```

The access model is therefore:

```text
Azure Data Factory
        │
        │ Managed Identity
        ▼
Azure RBAC
        │
        ▼
stlakehousebello
```

The pipeline does not require an embedded storage account key for this validation.

This establishes a more appropriate cloud identity pattern for the portfolio architecture.

**Result: PASS**

---

## Day 1 Gate 4 — ADF Source and Sink Validation

A small validation source file was used:

```text
adf_source.csv
```

Example content:

```csv
event_id,event_type
adf-day1-001,adf_validation
```

The file was configured as the source for an Azure Data Factory pipeline.

The destination was the project ADLS Gen2 account under:

```text
healthcare/raw/
```

The pipeline was validated successfully in ADF:

```text
ADF Source
    ↓
ADF Copy Activity
    ↓
ADLS Gen2
    ↓
healthcare/raw/
```

The pipeline validation returned:

```text
Your pipeline has been validated. No errors were found.
```

The pipeline was then published successfully.

A pipeline run was executed and the resulting file was verified in:

```text
healthcare/raw/
```

**Result: PASS**

This is the first working cloud-managed batch ingestion path in the project.

---

## Day 1 Gate 5 — ADF Trigger Validation

The ADF pipeline was successfully executed after publication using the ADF trigger/run mechanism.

The copied file appeared in the target ADLS `healthcare/raw/` location.

This validates that the orchestration layer can execute the ingestion activity rather than merely validate its configuration.

**Result: PASS**

---

## Day 1 Gate 6 — Terraform Foundation

Terraform was evaluated as the infrastructure-as-code foundation for the project.

A safe Terraform smoke test was performed without modifying the existing Azure infrastructure.

The test configuration declared the AzureRM provider:

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}
```

The following commands completed successfully:

```bash
terraform init
terraform validate
terraform plan
```

Terraform initialized AzureRM provider version:

```text
4.81.0
```

Validation returned:

```text
Success! The configuration is valid.
```

The plan returned:

```text
No changes. Your infrastructure matches the configuration.
```

### Important interpretation

Because the smoke-test configuration contained **no Azure resources**, the `terraform plan` result does not mean that Terraform currently manages or reconciles the existing project infrastructure.

It demonstrates that:

* Terraform is installed and operational.
* The AzureRM provider can initialize successfully.
* The configuration syntax is valid.
* Terraform can evaluate the current provider configuration without proposing changes.

Existing Azure resources have **not** yet been imported into Terraform state.

No `terraform apply` was performed.

**Result: PASS — Terraform foundation validated.**

Accurate interview wording:

> "I initialized Terraform with the AzureRM provider and validated the configuration against my Azure environment. I have not yet brought the existing Azure resources under Terraform state."

Future Terraform work may selectively import existing resources or manage newly created resources where it adds value. The project will not recreate working infrastructure solely to demonstrate Terraform.

---

# Day 1 Architecture Update

Day 1 expanded the Day 0 architecture by adding Azure Data Factory as the batch orchestration layer.

The current high-level ingestion architecture is:

```text
                         DATA SOURCES
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
             Batch/API              CDC / Events
                  │                       │
                  ▼                       ▼
                 ADF                 Python Producer
                  │                       │
                  │                       ▼
                  │                 Azure Event Hubs
                  │                 Kafka-compatible
                  │                       │
                  │                       ▼
                  │                 Python Consumer
                  │                       │
                  └───────────┬───────────┘
                              ▼
                         ADLS Gen2
                     stlakehousebello
                        /healthcare
                              │
                              ▼
                     Data Quality Gate
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
               Valid                  Invalid
                  │                       │
                  ▼                       ▼
               Bronze                Quarantine
                  │
                  ▼
                Silver
                  │
                  ▼
                 Gold
                  │
          ┌───────┴────────┐
          │                │
          ▼                ▼
 Synapse Serverless   ML-ready data
          │                │
          ▼                ▼
      Power BI       Databricks Free
                       Edition
                          │
                          ▼
                    ML Predictions
                          │
                          ▼
                       ADLS
                          │
                          ▼
                   Synapse Serverless
                          │
                          ▼
                       Power BI
```

---

# Current Service Responsibilities

| Service                 | Responsibility                                 |
| ----------------------- | ---------------------------------------------- |
| Azure Resource Group    | Logical resource boundary                      |
| ADLS Gen2               | Primary lake storage                           |
| Azure Data Factory      | Batch ingestion and orchestration              |
| Azure Event Hubs        | Streaming event ingestion                      |
| Python Producer         | CDC fixture replay                             |
| Python Consumer         | Kafka consumption, validation and lake handoff |
| Databricks Free Edition | PySpark transformation and ML execution        |
| Synapse Serverless SQL  | SQL query, validation and serving layer        |
| Power BI Desktop        | Analytics and visualization                    |
| Terraform               | Infrastructure-as-code foundation              |
| dbt                     | Evaluated but not selected as core runtime     |

---

# Current Data Lake Layout

```text
stlakehousebello
└── healthcare/
    ├── raw/
    │
    ├── bronze/
    │
    ├── silver/
    │
    ├── gold/
    │
    └── quarantine/
```

### Intended layer responsibilities

**Raw**

Original source data or minimally altered ingestion output.

**Bronze**

Validated and ingestion-enriched records, preserving source-level information and ingestion metadata.

**Silver**

Cleaned, standardized and deduplicated analytical records.

**Gold**

Business-ready analytical datasets and aggregates for reporting and downstream analytics.

**Quarantine**

Records rejected by ingestion or data-quality rules and retained for investigation rather than silently discarded.

---

# Day 0 + Day 1 Validation Evidence

## ADLS Gen2

```text
stlakehousebello
└── healthcare/
    ├── raw/
    ├── bronze/
    ├── silver/
    ├── gold/
    └── quarantine/
```

Validated:

```text
Synapse Serverless
        ↓
stlakehousebello/healthcare/raw/
        ↓
OPENROWSET
        ↓
Rows returned
        ↓
PASS
```

Day 1 additionally validated:

```text
ADF
 ↓
ADLS Gen2
 ↓
healthcare/raw/
 ↓
File copied successfully
 ↓
PASS
```

---

## Event Hubs

```text
eh-lakehouse-bello
        │
        ▼
healthcare-events
        │
        ▼
Kafka-compatible endpoint
        │
        ├── Python Producer
        │
        └── Python Consumer
        │
        ▼
PASS
```

---

## Synapse Serverless

```text
syn-lakehouse-bello-ondemand.sql.azuresynapse.net
        ↓
Explicit ADLS path
        ↓
CSV rows returned
        ↓
PASS
```

---

## Power BI

```text
Power BI
    ↓
Synapse Serverless endpoint
    ↓
Connection/authentication accepted
    ↓
PASS
```

This remains a connectivity validation only. The final analytical dashboard is not yet complete.

---

## dbt

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

## Databricks

```text
Databricks Free Edition
        ↓
Environment validated
        ↓
Planned PySpark / ML execution
        ↓
PASS
```

The project does not make critical Azure ingestion dependent on direct external connectivity from Databricks Free Edition.

---

## Azure Data Factory

```text
ADF
 ↓
Copy Activity
 ↓
ADLS Gen2
 ↓
healthcare/raw/
 ↓
File verified
 ↓
PASS
```

---

## Terraform

```text
Terraform
    ↓
AzureRM provider initialization
    ↓
Configuration validation
    ↓
Plan evaluation
    ↓
PASS
```

Terraform has **not** yet been used to manage the existing Azure resources.

---

# Day 1 Status

**Day 1 core Azure infrastructure and batch-ingestion validation completed.**

Validated:

* ADLS Gen2 project storage
* ADLS `quarantine` layer
* Azure Data Factory
* ADF managed identity
* Azure RBAC for ADF → ADLS
* ADF source/sink configuration
* ADF pipeline validation
* ADF pipeline execution
* File delivery into `healthcare/raw/`
* Event Hubs Kafka connectivity from Day 0
* Synapse Serverless connectivity from Day 0
* Power BI connectivity from Day 0
* Databricks Free Edition environment from Day 0
* Terraform AzureRM foundation

---

# Remaining Work

The following items are intentionally **not claimed as complete**:

* CDC fixture creation
* Python Event Hubs replay producer
* Python Kafka consumer for the project streaming flow
* Bronze streaming ingestion
* Event metadata preservation
* Duplicate detection by `event_id`
* Data-quality validation and quarantine workflow
* OpenFDA batch ingestion
* Bronze → Silver transformations
* Silver → Gold transformations
* Databricks PySpark implementation
* ML model development
* ML prediction output
* Synapse analytical views
* Power BI analytical dashboard
* CI/CD implementation
* Selective Terraform resource management/import
* Final end-to-end validation

---

# Cleanup Items

The following Day 0 temporary artifacts should be removed when convenient:

1. Temporary ADLS validation directory:

```text
healthcare/raw/_day0_validation/
```

2. Obsolete Event Hubs authorization rule:

```text
day0-kafka-plicy
```

3. Refresh the Event Hubs application connection string after the obsolete authorization rule is removed.

The old storage account:

```text
stlakehouse123
```

should **not** be deleted while the current Synapse workspace still references it as its immutable default data lake storage.

---

# Architecture Principles

The project follows these principles:

### 1. Separate ingestion from transformation

Azure Data Factory and Event Hubs handle ingestion/orchestration, while Databricks is used for transformation and ML workloads.

### 2. Prefer managed identity over embedded credentials

ADF accesses ADLS through its managed identity and Azure RBAC.

### 3. Preserve raw data

Raw ingestion is retained before transformation so that downstream processing can be reproduced or investigated.

### 4. Do not silently discard bad data

Invalid records should be routed to quarantine for investigation.

### 5. Validate before scaling

Small, observable validation gates are completed before implementing the full pipeline.

### 6. Avoid unnecessary infrastructure

The project deliberately does not introduce infrastructure such as a Dedicated Synapse SQL Pool solely to accommodate dbt.

### 7. Do not overclaim platform capabilities

Databricks Free Edition is treated as a separate PySpark/ML execution environment rather than being represented as an Azure production runtime with capabilities that have not been validated.

### 8. Infrastructure changes should be controlled

Terraform is being introduced incrementally. Existing Azure resources will not be blindly recreated or overwritten simply to demonstrate IaC.

---

# Interview Summary

The project currently demonstrates the following engineering decisions:

> "I designed the Azure healthcare lakehouse with separate batch and streaming ingestion paths. Azure Data Factory handles batch orchestration, while Azure Event Hubs provides Kafka-compatible streaming ingestion. Both paths land data in ADLS Gen2, where data-quality controls separate valid data from quarantined records. Synapse Serverless provides SQL-based querying and validation without introducing a dedicated SQL warehouse. Databricks is used as the PySpark and ML environment, with its Free Edition connectivity constraints explicitly separated from the critical Azure ingestion path. I also evaluated dbt and Terraform rather than adding them blindly: dbt was not selected because the chosen Serverless architecture does not require a Dedicated SQL Pool, while Terraform has been validated as an IaC foundation without yet claiming that existing resources are under Terraform state."

---

# Overall Status

## Day 0

**COMPLETE**

The foundational Azure services, connectivity, architectural decisions and major platform constraints were validated.

## Day 1

**COMPLETE**

The core Azure batch-orchestration path was implemented and validated:

```text
Azure Data Factory
        ↓
ADLS Gen2
        ↓
healthcare/raw/
        ↓
File successfully delivered
```

The project is now ready for the Day 2 streaming vertical slice:

```text
CDC Fixture
      ↓
Python Replay Producer
      ↓
Azure Event Hubs
      ↓
Kafka Consumer
      ↓
ADLS Bronze
      ↓
Synapse Validation
```

No Silver, Gold, ML, or final Power BI implementation is claimed as complete at this stage.
