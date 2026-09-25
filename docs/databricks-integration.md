# Databricks Integration

## 1. Purpose

This document describes how Databricks Free Edition is used within the Healthcare Public Health Surveillance & Risk Analytics Lakehouse.

The document complements:

```text
docs/adr/ADR-005-databricks-free-edition-integration.md
```

ADR-005 records the architectural decision and platform constraint.

This document records the implementation boundary, data handoff, ML workflow, validation, and limitations observed during the project.

---

## 2. Role of Databricks

Databricks Free Edition is used as a dedicated ML and PySpark execution environment.

It is not the primary ingestion or orchestration platform.

The primary Azure data-engineering path remains:

```text
External Sources
      │
      ├───────────────┐
      ▼               ▼
     ADF          Event Hubs
      │               │
      ▼               ▼
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
      ├──────────────► Synapse Serverless
      │                       │
      │                       ▼
      │                   Power BI
      │
      ▼
 ML-ready dataset
      │
      ▼
Databricks Free Edition
```

This separation prevents the core Azure ingestion pipeline from depending on capabilities unavailable in the selected Free Edition environment.

---

## 3. Databricks Environment

The project uses Databricks Free Edition for ML experimentation and execution.

The primary notebook is:

```text
notebooks/Day6_OpenFDA_ML.ipynb
```

The notebook implements the openFDA ML workflow, including:

* Feature preparation
* Categorical and numerical preprocessing
* XGBoost classification
* Model evaluation
* Feature importance
* Isolation Forest anomaly detection
* SHAP-based model interpretation
* MLflow experiment/model tracking

The working dataset contains derived openFDA adverse-event features rather than PHI or clinical records.

---

## 4. Databricks Storage Boundary

Databricks Free Edition uses a managed Unity Catalog volume as the working storage boundary:

```text
/Volumes/workspace/default/openfda_ml/
```

The ML workflow uses this environment for:

```text
openfda_ml_features.parquet
openfda_ml_predictions.parquet
openfda_feature_importance.parquet
openfda_anomalies.parquet
```

This working storage boundary was selected because the Free Edition environment did not provide the required arbitrary ADLS configuration for the intended direct cloud-storage integration.

---

## 5. ADLS Integration Constraint

A provisioned Azure Databricks environment can be designed to integrate directly with Azure storage using supported identity and storage-integration mechanisms.

The selected Free Edition environment does not provide the same connectivity/configuration model.

In particular, the project could not rely on arbitrary Spark configuration such as:

```text
fs.azure.*
```

to establish the required direct ADLS integration.

Therefore, the project does not claim the following as an implemented capability:

```text
Databricks Free Edition
        │
        │ fully automated direct ADLS integration
        ▼
ADLS Gen2
```

Instead, the project explicitly maintains an integration boundary.

---

## 6. Implemented Data Handoff

The implemented ML workflow uses a controlled data handoff.

Conceptually:

```text
Prepared ML dataset
        │
        ▼
Databricks Free Edition
        │
        ▼
Managed Unity Catalog volume
        │
        ▼
ML Parquet outputs
        │
        │ controlled manual handoff
        ▼
ADLS Gen2
healthcare/ml/openfda/
```

The canonical ADLS ML layer contains:

```text
healthcare/
└── ml/
    └── openfda/
        ├── openfda_ml_features.parquet
        ├── openfda_ml_predictions.parquet
        ├── openfda_feature_importance.parquet
        └── openfda_anomalies.parquet
```

The manual handoff is a documented platform workaround.

It is not represented as the desired production orchestration pattern.

---

## 7. ML Outputs

The Databricks workflow produces four primary output datasets.

### 7.1 ML Features

```text
openfda_ml_features.parquet
```

Contains the engineered features used by the ML workflow.

The feature dataset contains:

```text
safetyreportid
patientonsetage
patientonsetageunit
patientsex
reportercountry
reporterqualification
number_of_reactions
number_of_drugs
transmission_year
transmission_month
reporting_delay_days
target_serious
drug_reaction_ratio
```

The `safetyreportid` field is retained for traceability but is not used as a predictive feature.

### 7.2 ML Predictions

```text
openfda_ml_predictions.parquet
```

Contains model predictions and associated identifiers/results required by the serving layer.

The output is used for analytical reporting rather than clinical decision-making.

### 7.3 Feature Importance

```text
openfda_feature_importance.parquet
```

Contains model-derived feature-importance information.

Feature importance describes the contribution or influence of features within the trained model.

It does not establish causality.

### 7.4 Anomalies

```text
openfda_anomalies.parquet
```

Contains Isolation Forest anomaly results.

The output identifies observations with unusual feature patterns within the analyzed sample.

An anomaly does not indicate:

* Fraud
* Causality
* Data manipulation
* Clinical danger
* Confirmed safety risk

---

## 8. Model Workflow

The ML workflow is:

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
```

---

## 9. Model Validation

The XGBoost model was evaluated using a 200-row holdout set.

Observed metrics were:

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 0.7800 |
| Precision | 0.7831 |
| Recall    | 0.7143 |
| F1        | 0.7471 |
| ROC-AUC   | 0.8759 |
| PR-AUC    | 0.8803 |

The majority-class baseline accuracy was 0.545.

The model results demonstrate the ML workflow rather than establishing production-level predictive performance.

The evaluation dataset is derived from the project sample and should not be interpreted as representative of the complete openFDA reporting population.

---

## 10. Feature Leakage Controls

The feature-engineering process explicitly excludes fields that would directly expose the target or introduce unacceptable leakage.

Excluded fields include:

```text
serious
seriousnessdeath
fulfillexpeditecriteria
patientdeathdate
companynumb
```

The target is:

```text
target_serious
```

The target is derived from the source `serious` field before the excluded source field is removed from the model feature set.

The `safetyreportid` field is retained for traceability but excluded from predictive features.

---

## 11. Explainability

SHAP is used to provide model-level and observation-level interpretability during ML experimentation.

Feature importance is also exported as a separate analytical dataset.

Interpretation must remain within the scope of the model and sample.

For example, a high model importance for `reportercountry_US` is a model/sample signal.

It should not be interpreted as evidence that country causes adverse-event seriousness.

Potential explanations include differences in reporting practices, dataset composition, regulatory processes, and sample characteristics.

---

## 12. Anomaly Detection

Isolation Forest is configured as:

```text
n_estimators = 200
contamination = 0.05
random_state = 42
n_jobs = -1
```

The model was applied to the 200-row holdout sample.

Observed result:

```text
Rows analyzed: 200
Anomalies detected: 10
```

The anomaly output is intended for analytical review.

It is not a clinical risk classifier.

---

## 13. MLflow

MLflow is used within the Databricks ML workflow for experiment/model tracking capabilities available in the selected environment.

The purpose is to demonstrate model lifecycle practices such as recording experiment results and model-related metadata.

This portfolio implementation does not claim to provide a complete enterprise ML platform with production model registry governance, automated deployment, monitoring, or model approval workflows.

---

## 14. Serving Integration

After controlled handoff into ADLS, the ML outputs are exposed through Synapse Serverless SQL views.

The serving layer includes:

```text
dbo.vw_openfda_ml_predictions
dbo.vw_openfda_feature_importance
dbo.vw_openfda_anomalies
```

Power BI consumes these outputs for analytical reporting.

The resulting architecture is:

```text
Databricks Free Edition
        │
        ▼
ML Parquet outputs
        │
        │ controlled handoff
        ▼
ADLS Gen2
        │
        ▼
Synapse Serverless
        │
        ▼
Power BI
```

---

## 15. Why the Manual Handoff Is Acceptable for This Project

The manual handoff is a deliberate consequence of the selected Free Edition platform constraint.

It allows the project to demonstrate:

* Cloud data engineering
* Lakehouse layering
* ML feature engineering
* Distributed/PySpark-oriented ML execution
* Model evaluation
* Anomaly detection
* Explainability
* Analytical serving

without introducing an additional paid Azure Databricks environment.

The limitation is documented rather than hidden.

---

## 16. Production Evolution

A production implementation could replace Databricks Free Edition with a provisioned Azure Databricks environment.

The production architecture could then use supported:

* Managed identities
* External locations
* Cloud-storage integrations
* Automated orchestration
* Model lifecycle controls
* Monitoring
* Access governance

A possible target architecture is:

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
       ├── SHAP
       └── MLflow
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

The exact implementation would depend on the selected Azure Databricks configuration and enterprise identity/storage architecture.

---

## 17. Security Considerations

The Databricks notebook and exported artifacts must not contain:

* Azure connection strings
* Event Hubs credentials
* openFDA API keys
* SAS tokens
* Passwords
* Access tokens

ML outputs contain analytical results derived from public openFDA data.

The project does not use PHI or patient-identifiable clinical records.

Before committing the notebook to Git, notebook outputs should be reviewed for accidental credential exposure.

---

## 18. Limitations

This implementation has several deliberate limitations:

1. Databricks Free Edition is not treated as an equivalent replacement for a provisioned Azure Databricks workspace.
2. Direct automated ADLS integration from Free Edition is not claimed.
3. ML output handoff to the canonical ADLS ML layer is controlled and manual.
4. The ML evaluation uses a project-specific sample and holdout rather than a production validation population.
5. openFDA adverse-event reports do not establish causality or incidence.
6. ML predictions and anomaly scores are analytical outputs and not clinical decisions.
7. Enterprise ML governance, automated deployment, and production monitoring are outside the current scope.

---

## 19. Related Architecture Decision

The architectural decision governing this integration boundary is:

```text
docs/adr/ADR-005-databricks-free-edition-integration.md
```

ADR-005 explains why Databricks Free Edition is retained as a separate ML/PySpark environment and why the core Azure ingestion architecture does not depend on direct Free Edition connectivity.

This document explains how that decision was implemented.

---

## 20. Summary

The final integration boundary is:

```text
              AZURE DATA ENGINEERING
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
      ADF                      Event Hubs
       │                           │
       └─────────────┬─────────────┘
                     ▼
                   ADLS
                     │
             Bronze / Silver / Gold
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

The architecture deliberately separates Azure ingestion/orchestration from Databricks ML execution while maintaining ADLS as the common logical data boundary.

This reflects the actual capabilities and constraints of the selected project environment rather than assuming that a Free Edition environment provides the same integration capabilities as a provisioned production platform.
