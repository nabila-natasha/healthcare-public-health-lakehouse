# ADR-007: Databricks Free Edition Integration Boundary

**Status:** Accepted  
**Date:** 19 September 2026  
**Decision Type:** Architecture / Platform Constraint  

---

## Context

The project requires a machine-learning environment capable of supporting:

* PySpark
* feature engineering
* baseline modelling
* XGBoost
* Isolation Forest
* SHAP
* MLflow

Databricks Free Edition was selected as the available environment for this part of the project.

The broader Azure architecture contains:

* Azure Data Lake Storage Gen2
* Azure Event Hubs
* Azure Data Factory
* Synapse Serverless SQL
* Power BI

A standard Azure Databricks deployment could be designed as an integrated Azure compute layer with direct access to cloud storage and other Azure services.

However, the capabilities and connectivity available in Databricks Free Edition are not equivalent to those of a provisioned Azure Databricks workspace.

The project therefore needs an explicit integration boundary rather than assuming that Free Edition can serve as the primary cloud ingestion and transformation engine.

---

## Decision

Databricks Free Edition will be used as a **separate ML/PySpark execution environment** rather than as the primary Azure ingestion/orchestration engine.

The primary Azure data path will remain:

```text
External Sources
      │
      ├──────────────┐
      ▼              ▼
     ADF        Event Hubs
      │              │
      ▼              ▼
     ADLS ←──── Python Consumer
      │
      ▼
   Bronze
      │
      ▼
   Silver
      │
      ▼
    Gold
      │
      ├───────────────► Synapse Serverless
      │                       │
      │                       ▼
      │                   Power BI
      │
      ▼
 ML-ready dataset
      │
      ▼
Databricks Free Edition
      │
      ▼
 ML predictions / outputs
      │
      ▼
     ADLS
```

The project will not make the critical ingestion pipeline dependent on direct external connectivity from Databricks Free Edition.

---

## Rationale

### 1. Avoid unsupported assumptions

The architecture should reflect the actual capabilities of the selected platform.

A portfolio project should not claim production-style Azure Databricks integration when the selected Free Edition environment does not provide the same connectivity model.

### 2. Preserve the Azure ingestion architecture

ADF and Event Hubs remain useful regardless of the ML environment.

This allows the project to demonstrate genuine Azure data-engineering concepts:

```text
ADF
Event Hubs
ADLS
Synapse
RBAC
Managed Identity
```

without making them dependent on the ML environment.

### 3. Keep the ML workload realistic

Databricks Free Edition still provides a useful environment for demonstrating:

```text
PySpark
feature engineering
machine learning
XGBoost
Isolation Forest
SHAP
MLflow
```

The ML environment therefore remains part of the project without becoming an unsupported integration dependency.

### 4. Control project cost

Creating a separate Azure Databricks workspace solely to remove this boundary would introduce additional Azure infrastructure and potentially additional cost.

The project does not require that infrastructure to demonstrate its core engineering objectives.

---

## Alternatives Considered

### Alternative A — Direct ADLS → Databricks Free Edition

**Decision:** Not selected as the primary architecture.

Reason:

The project should not depend on external Azure connectivity that is unavailable or restricted in the selected Free Edition environment.

---

### Alternative B — Create Azure Databricks

**Decision:** Not selected for this project.

Reason:

The project is intentionally designed around a constrained Azure trial/free environment and does not require a full Azure Databricks workspace to demonstrate the planned ML concepts.

A future production architecture could replace Free Edition with Azure Databricks.

---

### Alternative C — Manual file transfer

**Decision:** Not selected as the desired production pattern.

Manual file transfer may be used only as a documented workaround if required by the Free Edition environment.

It must not be represented as the production orchestration pattern.

The Azure ingestion and data-processing architecture remains automated wherever the selected platform capabilities permit.

---

## Consequences

### Positive

* Keeps the Azure architecture internally coherent.
* Avoids unnecessary Azure infrastructure.
* Makes platform limitations explicit.
* Allows meaningful Databricks ML work.
* Preserves ADF, Event Hubs, ADLS and Synapse as genuine Azure components.
* Provides a clear architectural discussion for interviews.

### Negative

* Databricks Free Edition is not a fully integrated Azure compute layer.
* Some ML data hand-offs may require a staging mechanism or manual interaction depending on Free Edition capabilities.
* The architecture does not represent a production Azure Databricks deployment exactly.

---

## Future Production Evolution

If the project were moved to a production environment, Databricks Free Edition could be replaced with a provisioned Azure Databricks environment.

A production implementation could then use supported cloud-storage integrations, managed identities, external locations, and automated orchestration appropriate to the selected Databricks and Azure configuration.

The conceptual architecture could become:

```text
ADF / Event Hubs
       │
       ▼
     ADLS
       │
       ▼
Azure Databricks
       │
       ├── PySpark
       ├── ML
       └── MLflow
       │
       ▼
     ADLS
       │
       ▼
Synapse / Power BI
```

The exact production integration would depend on the selected Azure Databricks configuration, identity model, storage permissions, and orchestration approach.

That production migration is intentionally outside the scope of the current project.


---

## Validation

The integration boundary was validated during the ML implementation.

The project successfully demonstrated:

* Databricks Free Edition notebook execution.
* PySpark-based ML workflow execution.
* XGBoost classification.
* Isolation Forest anomaly detection.
* SHAP-based feature-importance analysis.
* MLflow experiment/model tracking capabilities used within the Databricks environment.
* Export of ML outputs as Parquet files.
* Controlled handoff of ML outputs into the canonical ADLS Gen2 ML layer.
* Synapse Serverless access to the resulting ML files.
* Power BI serving of ML predictions, feature-importance, and anomaly outputs.

The Databricks Free Edition environment did not provide the required arbitrary ADLS storage configuration for the intended direct integration pattern. Therefore, the project used a managed Unity Catalog volume as the Databricks working storage boundary and a controlled manual handoff for the resulting Parquet outputs.

The implemented workflow was therefore:

```text
ADLS / prepared ML dataset
        │
        │ controlled dataset handoff
        ▼
Databricks Free Edition
        │
        ├── ML feature engineering
        ├── XGBoost classification
        ├── Isolation Forest
        ├── SHAP
        └── MLflow
        │
        ▼
Managed Unity Catalog volume
        │
        │ controlled Parquet export
        ▼
ADLS Gen2 ML layer
        │
        ▼
Synapse Serverless
        │
        ▼
Power BI
```

This validates the architectural boundary while making the Free Edition limitation explicit.

The implementation does **not** claim fully automated Databricks-to-ADLS orchestration.

---

## Final Decision

**Accepted:**

Databricks Free Edition remains part of the project for PySpark and ML workloads, but the primary Azure ingestion and orchestration path will not depend on direct external connectivity from Databricks Free Edition.

The architecture therefore separates:

```text
Azure Data Engineering
        +
Databricks Free Edition ML
```

while maintaining ADLS as the common logical data boundary.
