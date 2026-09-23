# Day 6 — OpenFDA Analytics & Machine Learning

## 1. Objective

Day 6 extends the healthcare/public-health lakehouse from batch and streaming data engineering into analytical machine learning.

The primary analytical dataset is the FDA adverse event dataset obtained through the openFDA API.

The objective is to demonstrate an end-to-end machine-learning workflow using a controlled 1,000-report analytical sample:

1. Prepare model-ready features from the OpenFDA Silver layer.
2. Classify whether an adverse-event report is marked as serious.
3. Detect unusual reports using unsupervised anomaly detection.
4. Explain supervised model predictions using SHAP.
5. Track model experiments and metrics using MLflow.
6. Publish ML outputs back to the lakehouse for downstream analytics.

This project is intended as a portfolio and engineering demonstration. It is not a clinical decision-support system.

---

## 2. Analytical Scope

The project uses a controlled sample of:

* 1,000 CDC surveillance records
* 1,000 OpenFDA adverse-event reports

The 1,000-record OpenFDA sample is used consistently across the RAW, Bronze, Silver, Gold, and ML layers.

The sample size is intentionally controlled to make the project reproducible and suitable for a time-boxed portfolio implementation.

The project does not claim that the 1,000 records represent the complete openFDA dataset.

The CDC dataset remains primarily focused on streaming/event-engineering and surveillance analytics.

OpenFDA is the primary machine-learning workload.

---

## 3. Current Architecture

```text
                         DATA SOURCES
                             |
             +---------------+---------------+
             |                               |
             v                               v
       CDC archived data                openFDA API
             |                               |
             |                               v
             |                       Azure Data Factory
             |                               |
             v                               v
       Azure Event Hubs                 ADLS RAW
             |                               |
             v                               v
       Python Consumer                Python Bronze
             |                               |
             v                               v
        ADLS Bronze                    ADLS Bronze
             |                               |
             v                               v
        CDC Silver                    OpenFDA Silver
             |                         /      |      \
             v                        v       v       v
        CDC Gold                 Events   Reactions  Drugs
                                       \       |       /
                                        \      |      /
                                         v     v     v
                                      ML Feature
                                      Engineering
                                           |
                                           v
                                   ADLS ML Features
                                           |
                                           v
                                  Databricks Free Edition
                                           |
                         +-----------------+----------------+
                         |                 |                |
                         v                 v                v
                    Baseline           XGBoost       Isolation Forest
                         |                 |                |
                         |                 v                |
                         |               SHAP              |
                         |                 |                |
                         +-----------------+----------------+
                                           |
                                           v
                                         MLflow
                                           |
                                           v
                                   ML Prediction /
                                   Anomaly Outputs
                                           |
                                           v
                                         ADLS
                                           |
                                           v
                                       Synapse
                                           |
                                           v
                                      Power BI
```

---

## 4. OpenFDA Data Pipeline

The OpenFDA pipeline follows:

```text
openFDA API
    |
    v
ADF REST ingestion
    |
    v
ADLS RAW
    |
    v
Python Bronze transformation
    |
    v
ADLS Bronze
    |
    v
Python Silver transformation
    |
    +-------------------------------+
    |               |               |
    v               v               v
events.parquet  reactions.parquet  drugs.parquet
    |               |               |
    +---------------+---------------+
                    |
                    v
             Python ML feature
                engineering
                    |
                    v
           openfda_ml_features.parquet
```

---

## 5. Controlled OpenFDA Sample

The current analytical sample contains:

* 1,000 adverse-event reports
* 2,749 reaction records
* 3,079 drug records

The OpenFDA Silver layer maintains separate datasets because the source has different logical grains.

### Adverse-event report grain

One row represents one adverse-event report.

### Reaction grain

One row represents one reaction associated with an adverse-event report.

### Drug grain

One row represents one drug associated with an adverse-event report.

The ML feature dataset returns these related datasets to a single report-level grain.

---

## 6. ML Feature Dataset

The ML feature dataset is:

```text
ml/openfda/openfda_ml_features.parquet
```

It contains one row per `safetyreportid`.

Current columns:

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

---

## 7. Feature Engineering

### 7.1 Patient attributes

The feature dataset retains:

* patient age
* patient age unit
* patient sex

Missing values are retained for later preprocessing rather than deleting the entire report.

The current sample contains:

* 341 missing patient-age values
* 4 missing patient-sex values
* 7 missing reporter-qualification values

The ML pipeline will handle missing values during model preprocessing.

---

## 8. Child-table Aggregation

The reaction and drug datasets contain multiple records per adverse-event report.

They are aggregated to report level using:

```text
number_of_reactions
number_of_drugs
```

This allows the ML dataset to retain information from the normalized Silver layer without duplicating the report-level target.

---

## 9. Derived Features

### Transmission year

Derived from the OpenFDA transmission date.

### Transmission month

Derived from the OpenFDA transmission date.

### Reporting delay

Calculated as the difference between the transmission date and received date.

### Drug/reaction ratio

Calculated as:

```text
number_of_drugs / number_of_reactions
```

A zero reaction count is protected against division by zero.

---

## 10. Target Definition

The supervised-learning target is:

```text
target_serious
```

The source `serious` field is normalized to binary form:

```text
0 = report is not marked serious
1 = report is marked serious
```

Current distribution:

```text
0 = 546
1 = 454
```

Therefore:

```text
Non-serious: 54.6%
Serious:     45.4%
```

The target is sufficiently represented in both classes for a controlled portfolio classification demonstration.

---

## 11. Target Leakage Controls

The following fields are not used as predictive features because they may directly encode or strongly overlap with the seriousness outcome:

```text
seriousnessdeath
patientdeathdate
fulfillexpeditecriteria
```

The following identifier is retained only for traceability:

```text
safetyreportid
```

It is excluded from model training.

The target itself is also excluded from the model feature matrix:

```text
target_serious
```

The project will review feature availability and leakage before interpreting model performance.

---

## 12. Model Objective

The supervised learning question is:

> Can characteristics available in an adverse-event report distinguish reports that are marked as serious from reports that are not marked as serious?

This is a classification task.

The model does not determine whether a drug caused an adverse event.

The model predicts a classification based on characteristics present in the analytical dataset.

---

## 13. Baseline Model

A simple majority-class baseline will be established before using machine learning.

The baseline answers:

> How well can we perform without learning relationships between the features?

This provides a reference point for evaluating the XGBoost model.

---

## 14. Supervised Model

The primary supervised model is XGBoost.

The planned workflow is:

```text
ML feature dataset
       |
       v
Train/test split
       |
       v
Preprocessing
       |
       v
XGBoost classifier
       |
       v
Predictions
       |
       v
Evaluation
```

The train/test split will preserve the target class distribution using stratification.

The model will be evaluated using multiple metrics rather than accuracy alone.

Planned metrics:

* Accuracy
* Precision
* Recall
* F1 score
* ROC-AUC
* PR-AUC
* Confusion matrix

Because the target represents reported seriousness, recall and precision are considered alongside overall accuracy.

---

## 15. Unsupervised Anomaly Detection

Isolation Forest will be used as a separate analytical workflow.

The question is:

> Which adverse-event reports have feature combinations that appear unusual relative to the other reports?

This is different from the supervised classification problem.

The anomaly model does not require `target_serious`.

The outputs will include an anomaly indicator and anomaly score.

---

## 16. Model Explainability

SHAP will be used to explain the supervised XGBoost model.

The objective is to understand which features contributed to model predictions.

The project will distinguish between:

```text
model association / contribution
```

and:

```text
causal effect
```

SHAP explanations will not be interpreted as evidence that a drug or characteristic causes an adverse event.

---

## 17. MLflow Experiment Tracking

MLflow will be used to record the machine-learning experiment.

The experiment will capture:

* model type
* model parameters
* evaluation metrics
* model artifacts
* explainability artifacts where appropriate

The intended experiment structure is:

```text
OpenFDA ML Experiment
|
+-- Majority Baseline
|
+-- XGBoost Classifier
|
+-- Isolation Forest
|
+-- Evaluation Metrics
|
+-- SHAP Artifacts
```

---

## 18. Missing Data Strategy

Missing values will not automatically cause records to be discarded.

The current ML feature dataset contains:

```text
patientonsetage          341 missing
patientsex                 4 missing
reporterqualification      7 missing
```

The preprocessing pipeline will handle numeric and categorical missing values separately.

The chosen imputation strategy will be documented with the model implementation.

---

## 19. Data Quality Checks

The ML feature dataset must satisfy:

```text
1. One row per safetyreportid
2. No duplicate safetyreportid
3. target_serious is not null
4. target_serious contains only 0 and 1
5. number_of_reactions is non-negative
6. number_of_drugs is non-negative
7. transmission_year is populated
8. transmission_month is populated
9. No identifier is used as a predictive feature
10. Leakage-prone fields are excluded
```

---

## 20. Limitations

The OpenFDA adverse-event dataset has important analytical limitations.

Adverse-event reports are spontaneous safety reports and are subject to reporting and selection biases.

A report does not establish that a drug caused the reported reaction.

Therefore this project does not estimate:

* drug causality
* adverse-event incidence
* population-level risk
* clinical effectiveness
* patient-level clinical outcomes

The ML results should be interpreted as an engineering and analytical demonstration using a controlled sample.

The 1,000-report dataset is not intended to represent the complete OpenFDA reporting population.

---

## 21. Reproducibility

The project maintains a controlled 1,000-report analytical sample.

The same sample is used consistently through:

```text
RAW
Bronze
Silver
Gold
ML features
```

This allows the transformation and ML workflow to be reproduced without depending on a changing external API response.

OpenFDA API pagination beyond the current controlled sample is maintained as a future engineering enhancement.

---

## 22. Engineering Outcome

Day 6 extends the lakehouse from data engineering into machine-learning engineering.

The project demonstrates:

* API ingestion
* Azure Data Factory orchestration
* ADLS Gen2 storage
* medallion architecture
* normalized Silver datasets
* report-level feature engineering
* supervised classification
* unsupervised anomaly detection
* model explainability
* experiment tracking
* downstream lakehouse integration

The resulting architecture separates:

```text
data ingestion
data transformation
feature engineering
model training
model explainability
model tracking
business analytics
```

rather than combining all processing into a single notebook.
