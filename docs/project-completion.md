# Project Completion Record

## Project

**Healthcare Public Health Surveillance & Risk Analytics Lakehouse**

Repository: `nabila-natasha/healthcare-public-health-lakehouse`

Status: **Completed**

Completion date: September 2026

---

## 1. Project Objective

This project implements an Azure-based healthcare and public-health analytics lakehouse using public and synthetic data.

The objective was to demonstrate an end-to-end data engineering workflow covering:

* Batch ingestion
* Streaming ingestion
* Data lake storage
* Medallion architecture
* Data quality validation
* Analytical serving
* Machine learning
* Explainability
* Anomaly detection
* Business intelligence
* Security and governance
* CI/CD
* Infrastructure-as-code foundations

The project deliberately uses public and synthetic data and does not contain PHI or real patient-identifiable information.

---

## 2. Implemented Architecture

### Batch Ingestion

* Azure Data Factory
* openFDA adverse-event API
* REST pagination using `skip`
* ADLS Gen2 RAW layer

### Streaming Ingestion

* Azure Event Hubs using the Kafka protocol
* Historical CDC public-health data replayed at an accelerated cadence
* Event time and ingestion time preserved
* Synthetic duplicate, delayed, and malformed events used for validation

The CDC source is historical archived data and is not represented as a genuine live CDC feed.

---

## 3. Data Lakehouse Layers

The project uses a medallion-style architecture:

```text
RAW
  ↓
BRONZE
  ↓
SILVER
  ↓
GOLD
  ↓
ML / SERVING
```

### RAW

Original ingested data.

### BRONZE

Validated and normalized ingestion records.

### SILVER

Structured analytical entities and relationships.

### GOLD

Business-facing analytical datasets.

### ML

Machine-learning features, predictions, feature importance, and anomaly outputs.

---

## 4. openFDA Pipeline Results

The openFDA Azure Data Factory pipeline was validated using four paginated API requests.

### Validation Results

| Metric                   | Result |
| ------------------------ | -----: |
| API pages                |      4 |
| Reports retrieved        |  4,000 |
| Unique `safetyreportid`  |  4,000 |
| Duplicate reports        |      0 |
| Combined RAW JSON output | 1 file |
| ADF `rowsRead`           |      4 |

`ADF rowsRead = 4` represents the four REST response pages, not four individual reports.

The pipeline successfully demonstrated paginated batch ingestion into ADLS Gen2.

The current implementation uses a fixed sink filename. A future production implementation would use run-date or execution-specific paths to prevent scheduled executions from overwriting previous outputs.

---

## 5. CDC Streaming Results

The CDC streaming pipeline was validated using historical public-health surveillance data replayed through Event Hubs.

### Final Validation

| Metric             |               Result |
| ------------------ | -------------------: |
| RAW events         |                1,002 |
| Bronze events      |                1,000 |
| Quarantined events |                    1 |
| Duplicate delivery | Detected and handled |
| Malformed event    |          Quarantined |
| Delayed event      |  Detected and logged |

The implementation preserves both:

* `event_time`
* `ingestion_time`

This allows event-time and ingestion-time behavior to be distinguished during streaming validation.

---

## 6. Data Transformation

Python and Pandas were used for transformation and validation logic.

Implemented transformations include:

* CDC Bronze → Silver
* CDC Silver → Gold
* openFDA Bronze → Silver
* openFDA Silver → Gold
* openFDA ML feature engineering

Parquet was selected for analytical datasets because it provides typed, columnar storage suitable for downstream analytical processing.

---

## 7. Machine Learning

The openFDA ML workflow includes:

* Feature engineering
* Categorical encoding
* Numerical preprocessing
* XGBoost classification
* Isolation Forest anomaly detection
* Feature importance analysis
* SHAP explainability
* MLflow experiment tracking

The classification target is whether an adverse-event report is classified as serious.

### Recorded XGBoost Holdout Results

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 0.7800 |
| Precision | 0.7831 |
| Recall    | 0.7143 |
| F1        | 0.7471 |
| ROC-AUC   | 0.8759 |
| PR-AUC    | 0.8803 |

The evaluation used a 200-row holdout set.

### Confusion Matrix

```text
True Negative  = 91
False Positive = 18
False Negative = 26
True Positive   = 65
```

These results are recorded from this project's dataset and evaluation setup. They should not be interpreted as evidence of general clinical performance.

---

## 8. ML Data Leakage Controls

The feature-engineering process explicitly excludes fields that could leak the target or introduce post-outcome information.

Examples include:

* `serious`
* `seriousnessdeath`
* `fulfillexpeditecriteria`
* `patientdeathdate`
* `companynumb`

The report identifier `safetyreportid` is retained for traceability but is not used as a predictive feature.

The model therefore separates analytical traceability from predictive inputs.

---

## 9. Anomaly Detection

Isolation Forest was used as an anomaly-screening technique.

### Configuration

| Parameter           |   Value |
| ------------------- | ------: |
| Estimators          |     200 |
| Contamination       |    0.05 |
| Random state        |      42 |
| Parallel processing | Enabled |

### Validation

| Metric                 | Result |
| ---------------------- | -----: |
| Holdout rows evaluated |    200 |
| Anomalies identified   |     10 |

The anomaly output is intended for analytical review of unusual feature patterns.

It does not establish fraud, causality, or clinical risk.

---

## 10. Databricks Integration

Databricks Free Edition was used as the ML experimentation environment.

The ML workflow produced:

* ML features
* Predictions
* Feature importance
* Anomaly results

The Free Edition environment imposes limitations on direct ADLS integration using arbitrary Spark filesystem configuration.

Therefore, the project uses a documented controlled handoff from the Databricks-managed Unity Catalog volume to the canonical ADLS ML layer.

This is explicitly documented as a portfolio-environment workaround rather than a claim of fully automated production Databricks-to-ADLS orchestration.

---

## 11. Analytical Serving

Azure Synapse Serverless SQL provides the analytical serving layer.

Implemented views include:

* `dbo.vw_openfda_ml_predictions`
* `dbo.vw_openfda_analytics`
* `dbo.vw_openfda_feature_importance`
* `dbo.vw_openfda_anomalies`

These views provide downstream access to analytical and ML outputs without requiring a dedicated SQL pool.

---

## 12. Power BI

Power BI Desktop was used as the business-facing analytical layer.

The dashboard includes analytical views covering:

* openFDA adverse-event reporting
* ML predictions
* Model metrics
* Feature importance
* Anomaly screening

The Power BI `.pbix` file is maintained as a local portfolio artifact and is not stored in the GitHub repository.

The dashboard is an analytical reporting interface and is not presented as a clinical monitoring or clinical decision-support system.

---

## 13. Security and Governance

The project implements documented security practices including:

* Least-privilege access
* Azure RBAC
* Managed identity usage
* Secured ADF API-key parameterization
* Secret exclusion from Git
* Separation of RAW, BRONZE, SILVER, GOLD, and ML layers
* Quarantine handling
* ML leakage controls
* Read-oriented analytical serving

Known enterprise controls not implemented in this portfolio environment are documented separately, including:

* Azure Key Vault integration
* Private endpoints
* VNet integration
* Customer-managed keys
* Microsoft Purview
* Centralized SIEM integration
* Enterprise Databricks external locations

---

## 14. CI/CD

GitHub Actions provides automated repository validation.

CI performs:

* Dependency installation
* Python compilation
* Whitespace validation
* Pytest execution

The repository test suite completed successfully:

```text
26 passed
```

A controlled manual CD workflow was also implemented for release validation.

The CD workflow validates a selected Git reference but does not automatically recreate or destroy Azure infrastructure.

---

## 15. Infrastructure as Code

A Terraform foundation was added under:

```text
infra/terraform/
```

It includes:

* Provider configuration
* Project variables
* Outputs
* Terraform version constraints
* Provider lockfile
* Documentation

Terraform validation completed successfully.

The current Terraform configuration is intentionally a foundation rather than a claim that the entire Azure environment is already managed declaratively.

The existing Azure environment was provisioned incrementally during project development.

---

## 16. Final Validation

Final repository validation completed successfully.

### Repository

```text
Git working tree: clean
Branch: main
Remote: origin/main
```

### Tests

```text
26 passed
```

### Python Compilation

```text
python -m compileall ingestion scripts transformations
```

Completed without errors.

### Terraform

```text
terraform fmt -check
terraform validate
```

Completed successfully.

### Azure Resources

Validated resources include:

* Resource group: `rg-lakehouse-portfolio`
* ADLS Gen2: `stlakehousebello`
* Event Hubs namespace: `eh-lakehouse-bello`
* Event Hub: `healthcare-events`
* Synapse workspace: `syn-lakehouse-bello`
* Data Factory: `adf-lakehouse-bello`

The Azure resources reported successful provisioning states during final validation.

---

## 17. Known Limitations

The project intentionally documents several limitations.

### Data

* CDC data is historical archived surveillance data.
* The CDC stream is a replay simulation rather than a genuine live production feed.
* openFDA adverse-event reports are subject to reporting and selection bias.
* Adverse-event reports do not establish causality.
* The ML dataset is relatively small and should not be treated as a production-grade clinical model.

### Infrastructure

* Terraform does not yet manage the complete Azure environment.
* Databricks Free Edition prevents the desired fully automated ADLS integration pattern.
* The openFDA ADF sink currently uses a fixed filename.
* Enterprise security controls such as Key Vault and private networking are not implemented.

### Analytics

* ML results are dataset-specific.
* Feature importance describes model behavior in this experiment and should not be interpreted as causal evidence.
* Anomaly detection identifies unusual feature patterns rather than confirmed real-world risk.

---

## 18. Future Production Evolution

A production-oriented implementation could evolve toward:

1. Fully managed Terraform infrastructure.
2. Azure Key Vault-backed secret management.
3. Private endpoints and network isolation.
4. Enterprise Databricks external locations.
5. Automated Databricks-to-ADLS orchestration.
6. Incremental/date-partitioned openFDA ingestion.
7. Automated data-quality monitoring.
8. Model registry and automated model promotion.
9. Centralized monitoring and alerting.
10. Microsoft Purview-based data governance.
11. Larger and more representative ML datasets.
12. Formal model validation and monitoring.

These are future engineering improvements rather than capabilities currently claimed by the project.

---

## 19. Completion Status

The planned portfolio implementation is complete.

### Completed Areas

* [x] Azure resource foundation
* [x] ADLS Gen2
* [x] Event Hubs streaming
* [x] Historical CDC replay
* [x] ADF openFDA batch ingestion
* [x] Medallion transformations
* [x] Data-quality validation
* [x] Synapse Serverless serving
* [x] XGBoost ML
* [x] Isolation Forest anomaly detection
* [x] SHAP explainability
* [x] MLflow experiment tracking
* [x] Databricks integration documentation
* [x] Power BI analytical layer
* [x] Security and governance documentation
* [x] CI/CD
* [x] Terraform foundation
* [x] Architecture documentation
* [x] Architecture decision records
* [x] Final repository validation

**Final status: Project completed and portfolio-ready, with documented environment and integration limitations.**
