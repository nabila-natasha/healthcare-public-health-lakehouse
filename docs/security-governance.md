# Security & Governance

## 1. Purpose

This document describes the security, access-control, data-governance, and scope controls applied to the **Healthcare Public Health Surveillance & Risk Analytics Lakehouse**.

The project uses public and synthetic data only. It does not process Protected Health Information (PHI), patient-identifiable clinical records, or production healthcare workloads.

The security design follows:

* least-privilege access
* identity-based authentication
* secret separation
* data-layer separation
* explicit documentation of platform limitations

This is a portfolio implementation and is **not** presented as a production healthcare security or compliance environment.

---

## 2. Security Principles

The project applies the following principles:

1. **Least privilege** — identities and roles receive only the permissions required for their intended workload.
2. **Identity-based authentication** — Azure managed identities and Azure RBAC are preferred over storage account keys where supported.
3. **Secret separation** — API keys, connection strings, passwords, and tokens are not committed to Git.
4. **Layered data access** — RAW, Bronze, Silver, Gold, and ML outputs have distinct purposes and controlled access paths.
5. **Data minimization** — only fields required for the analytical and ML objectives are retained downstream.
6. **Public-data-only scope** — the project intentionally excludes PHI and production clinical data.
7. **Auditability** — infrastructure, transformation logic, validation rules, data contracts, and architecture decisions are documented in Git.
8. **Honest platform boundaries** — free-tier and platform limitations are documented rather than represented as fully automated production capabilities.

---

## 3. Azure Identity and Access

### 3.1 Azure RBAC

Azure role-based access control (RBAC) is used to grant access to Azure resources without distributing long-lived storage credentials.

The project uses identity-based access for ADLS Gen2 operations where supported.

During development, the required Azure storage data-plane permission was assigned to the development identity to validate ADLS Gen2 read and write operations.

The access pattern is:

```text
User / workload identity
        |
        v
Azure RBAC
        |
        v
ADLS Gen2
```

This avoids embedding a storage account key in application code.

Access permissions are granted at the scope required for the workload rather than treating storage access as unrestricted.

### 3.2 Synapse Managed Identity

The Synapse workspace uses a managed identity to access the project ADLS Gen2 storage.

The project Synapse external data source is:

```text
HealthcareADLS
```

and points to the project storage account.

The Synapse managed identity was granted the required storage data access so that Synapse Serverless SQL can query analytical files in ADLS.

The access pattern is:

```text
Synapse Serverless SQL
        |
        | Managed Identity
        v
Azure RBAC
        |
        v
ADLS Gen2
```

This avoids embedding a storage account key in SQL scripts or repository files.

The Synapse workspace's default storage configuration is not treated as the canonical project data store. The project explicitly uses the linked project ADLS storage through the `HealthcareADLS` external data source.

---

## 4. Azure Data Factory Security

Azure Data Factory is used for scheduled openFDA batch ingestion.

The openFDA API key is handled as a secured dataset parameter rather than being committed to source control.

The repository documents the parameter and ingestion pattern but does not contain the actual API key.

The intended credential flow is:

```text
ADF
 |
 | secured API parameter
 v
openFDA REST API
 |
 v
ADLS Gen2 RAW
```

The API key must never be placed in:

* Git commits
* README files
* Markdown documentation
* Python source files
* notebook outputs
* screenshots
* GitHub Actions logs

The current implementation demonstrates secure parameter separation. A production implementation could additionally use a centralized secret-management service such as Azure Key Vault.

---

## 5. Event Hubs Security

Azure Event Hubs is used for the simulated CDC streaming workload.

The producer and consumer use Event Hubs authentication rather than exposing broker credentials in source code.

Connection strings are treated as secrets and are supplied through environment variables during development.

Example environment-variable pattern:

```text
EVENT_HUB_CONNECTION_STRING=<secret>
```

The actual connection string is excluded from Git.

The Event Hubs namespace uses an authorization policy for application access rather than treating the namespace as an unrestricted endpoint.

The project uses Event Hubs with the Kafka protocol for the streaming demonstration while retaining Azure-managed authentication and authorization controls.

---

## 6. Secret Management

The repository contains configuration templates such as:

```text
.env.example
```

but does not contain production credentials.

Sensitive values include:

* Azure connection strings
* Event Hubs credentials
* openFDA API keys
* Azure subscription credentials
* SAS tokens
* passwords
* access tokens

These values are supplied through environment variables, Azure-secured parameters, or other runtime credential mechanisms.

The project follows the rule:

```text
Source code
    |
    +--> configuration names
    |
    +--> non-sensitive defaults
    |
    X--> secrets
```

Before committing notebooks or generated files, outputs must be reviewed for accidental exposure of credentials.

Notebook outputs are particularly important because interactive development can accidentally persist API keys, connection strings, or tokens in cell output.

---

## 7. GitHub Security

The repository uses GitHub Actions for automated validation.

CI performs:

* Python compilation
* repository whitespace validation
* automated tests

The CI workflow uses:

```yaml
permissions:
  contents: read
```

This follows the principle of granting the workflow only the repository permission required for its validation job.

The current CD workflow is intentionally manual and performs controlled release validation.

The CD workflow:

* validates a selected Git reference
* installs the project dependencies
* compiles Python source
* runs the test suite
* performs whitespace validation
* generates a release summary

It does not recreate, modify, or destroy the Azure environment.

Azure credentials are not embedded in the CI/CD workflow.

---

## 8. Data Classification

The project data is classified into the following broad categories:

| Data                           | Classification           | Purpose                            |
| ------------------------------ | ------------------------ | ---------------------------------- |
| CDC archived surveillance data | Public                   | Historical public-health analytics |
| openFDA adverse-event data     | Public                   | Safety-event analytics             |
| Synthetic CDC replay envelope  | Synthetic                | Streaming architecture simulation  |
| Bronze datasets                | Derived public/synthetic | Validated ingestion data           |
| Silver datasets                | Derived public/synthetic | Structured analytical data         |
| Gold datasets                  | Derived public/synthetic | Business-facing analytics          |
| ML features                    | Derived analytical       | Model training and inference       |
| ML predictions                 | Derived analytical       | Analytical screening               |
| ML anomaly outputs             | Derived analytical       | Unusual-pattern screening          |
| Credentials/secrets            | Confidential             | Runtime authentication             |

No PHI or patient-identifiable clinical data is intentionally introduced into the project.

The CDC dataset is an archived public-health surveillance dataset and is not a source of live patient monitoring data.

---

## 9. Data-Layer Governance

The lakehouse separates data according to processing stage:

```text
RAW
 |
 | source-preserving ingestion
 v
BRONZE
 |
 | validation / normalization
 v
SILVER
 |
 | business aggregation
 v
GOLD
 |
 +--> Power BI serving
 |
 +--> ML features
       |
       +--> predictions
       +--> feature importance
       +--> anomaly outputs
```

### 9.1 RAW

RAW contains source-oriented ingestion output.

For openFDA, the ADF pipeline writes the retrieved API response into the RAW layer.

For CDC, the streaming consumer writes the incoming event envelope into the RAW layer before downstream transformation.

RAW is intended to preserve the source-oriented representation needed for traceability and replay.

### 9.2 BRONZE

Bronze contains validated ingestion records.

For CDC, the Bronze event contract includes:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

Malformed CDC events are redirected to the quarantine layer instead of being silently inserted into Bronze.

### 9.3 SILVER

Silver contains structured and typed analytical data.

The transformation layer converts source-oriented Bronze data into Parquet datasets suitable for analytical processing.

### 9.4 GOLD

Gold contains curated business-facing analytical outputs.

These datasets are designed for reporting and downstream analytical consumption rather than source preservation.

### 9.5 ML

The ML layer contains:

```text
openfda_ml_features.parquet
openfda_ml_predictions.parquet
openfda_feature_importance.parquet
openfda_anomalies.parquet
```

These outputs are analytical artifacts and are not clinical records.

---

## 10. Data Quality and Quarantine

The CDC streaming pipeline validates the required event envelope before writing records to Bronze.

Required fields include:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

Malformed events are not silently inserted into Bronze.

During the Day 4 validation run:

```text
Messages received: 1002
Bronze records:     1000
Quarantined:           1
```

The invalid event was quarantined because a required event field was missing.

The streaming workload also intentionally included a duplicate delivery to demonstrate duplicate handling.

The CDC event identifier is deterministic:

```text
SHA-256(
    state
    |
    start_date
    |
    end_date
)
```

For the same CDC business key:

```text
state | start_date | end_date
```

the SHA-256 calculation produces the same 64-character event identifier.

This means that repeated delivery of the same source business event retains the same `event_id`.

The identifier is an event fingerprint, not an encoded representation of the payload and cannot be reversed to recover the source record.

---

## 11. CDC Event-Time and Ingestion-Time

The CDC streaming envelope intentionally preserves two timestamps:

```text
event_time
ingestion_time
```

`event_time` represents the source event timestamp.

For the CDC dataset, this is derived from the source `date_updated` field.

`ingestion_time` represents when the event entered the simulated streaming pipeline.

For example:

```text
event_time     = 2020-04-23T00:00:00.000
ingestion_time = 2026-09-21T05:42:36.901364+00:00
```

This distinction allows the project to identify delayed or late-arriving events without confusing source timing with pipeline processing timing.

The CDC source is historical archived data replayed at an accelerated cadence.

It does not represent a genuine real-time CDC feed.

The streaming architecture therefore demonstrates event-time and ingestion-time processing concepts without claiming access to a live CDC production stream.

---

## 12. ML Governance

The openFDA ML workflow is designed for analytical screening rather than clinical decision-making.

The XGBoost model predicts the project-defined:

```text
target_serious
```

classification target.

The feature-engineering process explicitly excludes fields that could directly leak the target into the model, including:

```text
serious
seriousnessdeath
fulfillexpeditecriteria
patientdeathdate
companynumb
```

The `safetyreportid` field is retained for traceability but is not used as a predictive feature.

The model therefore operates on the engineered feature set rather than directly using the source target or known outcome-related fields.

### 12.1 Important Interpretation Limitation

openFDA adverse-event reports are spontaneous safety reports.

They are subject to reporting and selection biases and do not establish:

* causality
* incidence
* prevalence
* clinical risk

Model predictions must therefore be interpreted as analytical model outputs rather than clinical determinations.

The project does not present the model as a clinical decision-support system.

---

## 13. Anomaly Detection Governance

Isolation Forest is used to identify observations with unusual feature patterns within the analyzed dataset.

The output contains:

```text
safetyreportid
anomaly_prediction
anomaly_score
is_anomaly
```

An anomaly flag means that the observation has an unusual combination of model features relative to the analyzed sample.

It does **not** mean:

* fraud
* causality
* data manipulation
* clinical danger
* confirmed safety risk
* confirmed adverse drug reaction

The dashboard therefore presents anomaly results as observations for analytical review.

The anomaly output should be investigated alongside source data and domain context rather than treated as a standalone conclusion.

---

## 14. Power BI Access

Power BI consumes curated analytical views from Synapse Serverless SQL.

The serving layer exposes views such as:

```text
vw_openfda_ml_predictions
vw_openfda_analytics
vw_openfda_feature_importance
vw_openfda_anomalies
```

Power BI is treated as a read-oriented presentation layer rather than an ingestion or transformation engine.

The dashboard presents:

* analytical metrics
* adverse-event aggregates
* model predictions
* feature importance
* anomaly observations

The dashboard is an analytical reporting interface.

It is not a:

* clinical monitoring system
* clinical decision-support system
* patient monitoring platform
* diagnostic system

Model and anomaly outputs are presented with appropriate analytical limitations.

---

## 15. Databricks Free Edition Constraint

Databricks Free Edition was used for ML experimentation through a managed Unity Catalog volume.

The required direct ADLS configuration was not available in the project's Free Edition environment.

Therefore, the current implementation uses:

```text
ADLS Silver
    |
    v
Databricks Free Edition
    |
    | ML experimentation
    v
Unity Catalog volume
    |
    | controlled manual handoff
    v
ADLS ML
    |
    v
Synapse Serverless
    |
    v
Power BI
```

The ML outputs were manually transferred into the canonical ADLS ML layer after experimentation.

This limitation is documented rather than hidden.

The project therefore does not claim a fully automated Databricks-to-ADLS production integration.

A production implementation would require a Databricks environment that supports the required external storage configuration, identity integration, and appropriate governance controls.

See [`docs/databricks-integration.md`](databricks-integration.md) for the detailed integration decision.

---

## 16. Retention

The Event Hubs namespace uses a seven-day retention period for the simulated streaming workload.

This is appropriate for the development and portfolio demonstration scope.

The retention period supports the streaming demonstration without treating Event Hubs as the system of record for long-term analytical storage.

Long-term analytical datasets are stored in ADLS according to their lakehouse layer and project requirements.

The project does not define a regulated healthcare records-retention policy because it does not process regulated clinical records or PHI.

Production implementations would require retention policies aligned with organizational, contractual, legal, and regulatory requirements.

---

## 17. Known Security and Governance Limitations

This is a portfolio implementation rather than a production healthcare platform.

The following enterprise controls are intentionally outside the current scope:

* Azure Key Vault integration
* private endpoints
* VNet integration
* customer-managed encryption keys
* Microsoft Purview catalog implementation
* centralized SIEM/SOC integration
* production-grade secret rotation
* enterprise identity lifecycle management
* formal regulatory compliance certification
* formal data-loss-prevention controls
* enterprise-wide security monitoring
* production disaster-recovery implementation
* production business-continuity procedures

These are identified as potential production hardening areas rather than claimed as implemented controls.

The absence of these controls should not be interpreted as evidence that the architecture is production-ready for regulated healthcare workloads.

---

## 18. Governance Summary

The project demonstrates the following security and governance practices:

* identity-based Azure access
* Azure RBAC
* Synapse managed identity
* secured ADF API parameters
* environment-based secret handling
* restricted GitHub Actions permissions
* data-layer separation
* malformed-event quarantine
* deterministic event identity
* event-time versus ingestion-time tracking
* CDC duplicate handling
* ML target-leakage controls
* traceability through source identifiers
* analytical rather than clinical interpretation of ML outputs
* explicit documentation of platform limitations
* public and synthetic data scope
* documented data contracts
* automated data-quality tests
* controlled release validation through GitHub Actions

The overall governance approach prioritizes:

```text
Traceability
     +
Least privilege
     +
Secret separation
     +
Data quality
     +
Explicit contracts
     +
Controlled access
     +
Honest limitation reporting
```

The project demonstrates engineering patterns that can be extended toward a production environment, while explicitly distinguishing the current portfolio implementation from a regulated production healthcare platform.
