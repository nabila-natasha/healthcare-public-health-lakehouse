# Day 6 — OpenFDA Analytics and Machine Learning

## 1. Objective

Day 6 extends the healthcare/public-health lakehouse from analytical Gold data into a machine-learning workflow using historical openFDA adverse-event reports.

The objective is to demonstrate an end-to-end ML analytics vertical slice:

```text
openFDA
   ↓
Azure Data Factory
   ↓
ADLS Gen2 RAW
   ↓
Bronze
   ↓
Silver
   ↓
ML feature engineering
   ↓
Databricks Free Edition
   ↓
XGBoost / Isolation Forest
   ↓
ML predictions
   ↓
ADLS ML layer
   ↓
Synapse Serverless SQL
   ↓
Power BI
```

The ML workload is intended as a portfolio demonstration of data preparation, leakage control, supervised classification, anomaly detection, model explainability, and downstream analytics serving.

This project does **not** provide clinical decision support, patient-level medical advice, or causal conclusions about drugs and adverse reactions.

---

## 2. Dataset Scope

The controlled Day 6 workload uses 1,000 openFDA adverse-event records.

The data was previously ingested through the Azure lakehouse pipeline:

```text
ADF → ADLS RAW → Bronze → Silver
```

The Silver layer contains three related Parquet datasets:

```text
healthcare/silver/openfda/
├── adverse_events.parquet
├── adverse_event_reactions.parquet
└── adverse_event_drugs.parquet
```

Observed Silver-layer volumes:

| Dataset               | Records |
| --------------------- | ------: |
| Adverse-event reports |   1,000 |
| Reaction records      |   2,749 |
| Drug records          |   3,079 |

The three datasets are combined at the adverse-event report grain for ML feature engineering.

---

## 3. ML Feature Dataset

The ML feature transformation is implemented in:

```text
transformations/ml/openfda_features.py
```

The feature dataset is:

```text
healthcare/ml/openfda/openfda_ml_features.parquet
```

During development, the controlled feature dataset was also loaded into a Databricks Unity Catalog volume for ML experimentation.

The ML dataset contains:

* 1,000 adverse-event reports
* 13 columns
* one row per adverse-event report

### Feature columns

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

### Derived features

`number_of_reactions` and `number_of_drugs` are aggregated from the Silver reaction and drug child tables.

`drug_reaction_ratio` is calculated as:

```text
number_of_drugs / number_of_reactions
```

with zero protection for reports without reactions.

`reporting_delay_days` represents the difference between the transmission date and received date in the source data.

---

## 4. Target Definition

The supervised learning target is:

```text
target_serious
```

It is derived from the source `serious` classification.

The target was normalized to a binary representation:

```text
0 = Not Serious
1 = Serious
```

Observed target distribution:

| Target      | Records | Percentage |
| ----------- | ------: | ---------: |
| Not Serious |     546 |      54.6% |
| Serious     |     454 |      45.4% |
| Total       |   1,000 |       100% |

The target is therefore reasonably balanced for this controlled sample.

---

## 5. Target Leakage Review

Before modelling, fields that could directly expose or strongly encode the target were excluded.

Excluded fields:

```text
serious
seriousnessdeath
fulfillexpeditecriteria
patientdeathdate
companynumb
```

`safetyreportid` was retained for traceability but excluded from the model feature matrix.

### Rationale

| Field                     | Treatment         | Reason                                                               |
| ------------------------- | ----------------- | -------------------------------------------------------------------- |
| `serious`                 | Excluded          | Source field used to construct the target                            |
| `seriousnessdeath`        | Excluded          | Closely related to seriousness/death classification                  |
| `fulfillexpeditecriteria` | Excluded          | Regulatory/reporting field potentially associated with seriousness   |
| `patientdeathdate`        | Excluded          | Contains outcome information                                         |
| `companynumb`             | Excluded          | Report/source identifier rather than a meaningful predictive feature |
| `safetyreportid`          | Traceability only | Identifier and not used as a model feature                           |

This leakage review was performed before the train/test modelling step.

---

## 6. Train/Test Design

The dataset was split into:

```text
80% training
20% test
```

with:

```text
random_state = 42
stratify = target_serious
```

This produced:

```text
Training records: 800
Test records:     200
```

Stratification was used to preserve the target-class distribution between training and test data.

The test set was held out for final model evaluation.

---

## 7. Preprocessing

The model contains both numerical and categorical variables.

Numerical variables were processed using median imputation.

Categorical variables were processed using:

1. most-frequent-value imputation
2. one-hot encoding

The preprocessing was implemented as part of the model pipeline so that transformations are fitted using the training data rather than independently transforming the entire dataset before the split.

This reduces the risk of preprocessing leakage.

---

## 8. Baseline Model

A majority-class `DummyClassifier` was used as the baseline.

Observed baseline performance:

| Model             | Accuracy | Precision | Recall |     F1 |
| ----------------- | -------: | --------: | -----: | -----: |
| Majority Baseline |   0.5450 |    0.0000 | 0.0000 | 0.0000 |
| XGBoost           |   0.7800 |    0.7831 | 0.7143 | 0.7471 |

The baseline accuracy of 0.545 reflects the majority class in the training/test population.

The baseline establishes a simple reference point before evaluating the more complex model.

---

## 9. XGBoost Model

The supervised classifier used XGBoost with the following configuration:

```text
n_estimators = 200
max_depth = 5
learning_rate = 0.05
subsample = 0.8
colsample_bytree = 0.8
objective = binary:logistic
eval_metric = logloss
random_state = 42
```

This configuration was selected as a controlled initial model rather than as the result of extensive hyperparameter optimisation.

### Test-set results

The model was evaluated on the 200-row holdout set.

| Metric    | Result |
| --------- | -----: |
| Accuracy  | 0.7800 |
| Precision | 0.7831 |
| Recall    | 0.7143 |
| F1        | 0.7471 |
| ROC-AUC   | 0.8759 |
| PR-AUC    | 0.8803 |

These metrics describe performance on this controlled sample only. They should not be interpreted as production performance or as evidence that the model would generalize to the broader adverse-event reporting population.

---

## 10. Confusion Matrix

The observed confusion matrix was:

```text
                    Predicted
                 Not Serious  Serious

Actual Not Serious      91       18
Actual Serious          26       65
```

Therefore:

```text
True Negative  = 91
False Positive = 18
False Negative = 26
True Positive   = 65
```

The model correctly identified 65 of the 91 serious reports in the holdout set.

It incorrectly classified 26 serious reports as not serious.

This illustrates why accuracy alone is insufficient when evaluating a classification model.

---

## 11. Feature Importance

The XGBoost model's highest feature-importance values were:

| Feature                                 | Importance |
| --------------------------------------- | ---------: |
| `reportercountry_US`                    |   0.430432 |
| `reporting_delay_days`                  |   0.088900 |
| `transmission_year`                     |   0.083958 |
| `transmission_month`                    |   0.054620 |
| `reporterqualification`                 |   0.042045 |
| `reportercountry_DE`                    |   0.039783 |
| `number_of_reactions`                   |   0.034327 |
| `reportercountry_COUNTRY NOT SPECIFIED` |   0.031618 |
| `patientonsetage`                       |   0.030828 |
| `patientonsetageunit_`                  |   0.029911 |

### Interpretation and limitation

`reportercountry_US` has substantially higher model feature importance than the other features in this controlled sample.

This should **not** be interpreted as evidence that reporting country causes adverse-event seriousness.

Possible explanations include:

* differences in reporting practices
* differences in dataset composition
* source-system characteristics
* regulatory/reporting processes
* sampling effects

The feature should therefore be treated as a model signal requiring further investigation rather than as a causal or clinical finding.

A larger and more representative dataset would be required before drawing stronger conclusions about feature stability or generalisation.

---

## 12. SHAP Explainability

SHAP was used to examine how individual features contributed to XGBoost predictions.

The SHAP analysis is intended to answer:

> Which features influenced the model's predictions, and in which direction?

SHAP explanations describe model behaviour.

They do not establish:

* drug causality
* clinical causation
* population-level risk
* treatment effectiveness

The SHAP summary plot was generated in the Databricks ML notebook.

<img width="823" height="940" alt="SHAP" src="https://github.com/user-attachments/assets/ba656950-decb-4388-af82-b43f7adc361a" />

---

## 13. Isolation Forest Anomaly Detection

A separate Isolation Forest model was used for unsupervised anomaly screening.

The objective is different from the XGBoost classification task.

### XGBoost

```text
Question:
Can the available features predict the serious/non-serious classification?
```

### Isolation Forest

```text
Question:
Which reports have feature combinations that appear unusual
relative to the rest of the sample?
```

Isolation Forest was configured with:

```text
n_estimators = 200
contamination = 0.05
random_state = 42
```

The model therefore flagged approximately 5% of the test population as anomalous.

The anomaly output included:

```text
anomaly_prediction
anomaly_score
is_anomaly
```

The lowest anomaly scores observed in the test sample included reports with unusual combinations of reporting delay, drug/reaction counts, age information, reporter country, and other features.

The Isolation Forest model identified these reports as unusual based on the engineered feature distribution. An `anomaly_prediction` of `-1` indicates an anomalous observation.

```text
|   patientonsetage |   patientonsetageunit |   patientsex | reportercountry       |   reporterqualification |   number_of_reactions |   number_of_drugs |   transmission_year |   transmission_month |   reporting_delay_days |   drug_reaction_ratio |   anomaly_prediction |   anomaly_score | is_anomaly   |
|------------------:|----------------------:|-------------:|:----------------------|------------------------:|----------------------:|------------------:|--------------------:|---------------------:|-----------------------:|----------------------:|---------------------:|----------------:|:-------------|
|               nan |                       |            2 | COUNTRY NOT SPECIFIED |                       5 |                     4 |                 2 |                2018 |                    3 |                   1469 |              0.5      |                   -1 |     -0.0854261  | True         |
|                38 |                   801 |            1 | GB                    |                       3 |                    10 |                 3 |                2016 |                    3 |                    723 |              0.3      |                   -1 |     -0.0504328  | True         |
|               nan |                       |          nan | US                    |                       5 |                     2 |                 8 |                2018 |                    5 |                   1518 |              4        |                   -1 |     -0.0490109  | True         |
|                74 |                   801 |            1 | SE                    |                       1 |                     2 |                 6 |                2018 |                    3 |                   1469 |              3        |                   -1 |     -0.0481415  | True         |
|                62 |                   801 |            1 | CN                    |                       3 |                     1 |                 1 |                2015 |                    3 |                    379 |              1        |                   -1 |     -0.0407216  | True         |
|               nan |                       |            2 | COUNTRY NOT SPECIFIED |                       5 |                     3 |                 8 |                2015 |                    5 |                    442 |              2.66667  |                   -1 |     -0.0258868  | True         |
|                42 |                   801 |            1 | COUNTRY NOT SPECIFIED |                       5 |                     6 |                 1 |                2015 |                    3 |                    379 |              0.166667 |                   -1 |     -0.013714   | True         |
|               nan |                       |            2 | COUNTRY NOT SPECIFIED |                       5 |                     2 |                 1 |                2015 |                    5 |                    442 |              0.5      |                   -1 |     -0.00812708 | True         |
|                69 |                   801 |            1 | JP                    |                       3 |                     2 |                 2 |                2015 |                    3 |                    379 |              1        |                   -1 |     -0.00602004 | True         |
|                68 |                   801 |            2 | AU                    |                       1 |                     7 |                16 |                2014 |                   10 |                    204 |              2.28571  |                   -1 |     -0.00251163 | True         |

```

An anomaly flag is a **screening signal**, not evidence of an error, fraud, unsafe product, or clinical danger.

---

## 14. Databricks ML Experimentation

The ML workflow was implemented in the Databricks Free Edition notebook:

```text
notebooks/Day6_OpenFDA_ML.ipynb
```

The notebook contains:

1. data loading
2. data-quality audit
3. target inspection
4. leakage review
5. preprocessing
6. train/test split
7. baseline model
8. XGBoost model
9. evaluation metrics
10. confusion matrix
11. feature importance
12. SHAP explainability
13. Isolation Forest anomaly detection
14. MLflow experiment tracking
15. ML prediction output generation

The notebook is version-controlled as part of the GitHub repository.

---

## 15. ML Prediction Output

The model generated predictions for the 200-row holdout test set.

The prediction dataset contains:

```text
safetyreportid
actual_serious
predicted_serious
predicted_probability
```

Example records served through Synapse:

```text
|safetyreportid   | actual_serious   | predicted_serious   | predicted_probability   |
| ----------------| -----------------|---------------------|-----------------------: |
| 10004170        | 1                | 1                   | 0.5010936               |
| 10003987        | 0                | 0                   | 0.13284644              |
| 10003952        | 1                | 0                   | 0.4744376               |
| 10003601        | 0                | 0                   | 0.19056003              |
| 10004152        | 1                | 1                   | 0.97840196              |
| 10003926        | 1                | 0                   | 0.26425228              |
| 10003792        | 1                | 1                   | 0.9257659               |
| 10003434        | 0                | 0                   | 0.05613183              |
| 10003665        | 0                | 0                   | 0.18527436              |
| 10004028        | 0                | 0                   | 0.46103808              |
```

`predicted_probability` represents the XGBoost probability assigned to the positive class (`Serious`).

The probability is a model output and has not been calibrated as a production risk probability.

---

## 16. ADLS ML Layer

The ML prediction output is stored in the ADLS ML layer:

```text
healthcare/ml/openfda/openfda_ml_predictions.parquet
```

The ML feature dataset is:

```text
healthcare/ml/openfda/openfda_ml_features.parquet
```

This creates a separation between:

```text
ML features
```

and:

```text
ML predictions
```

which allows downstream analytical systems to consume model outputs without requiring direct access to the Databricks notebook.

---

## 17. Synapse Serverless Serving Layer

Synapse Serverless SQL reads the ML prediction Parquet from ADLS.

The serving view is:

```text
dbo.vw_openfda_ml_predictions
```

The view exposes:

```text
safetyreportid
actual_serious
predicted_serious
predicted_probability
```

Example query:

```sql
SELECT TOP 20 *
FROM dbo.vw_openfda_ml_predictions;
```

This successfully returned ML prediction records from the Synapse serving layer.

The resulting architecture is:

```text
Databricks ML
      ↓
ADLS ML
      ↓
Synapse Serverless
      ↓
dbo.vw_openfda_ml_predictions
      ↓
Power BI
```

---

## 18. Power BI Foundation

Power BI consumes the Synapse serving view rather than connecting directly to the Databricks notebook.

The intended ML analytics page contains:

### KPI

Total ML prediction records.

### KPI

Predicted serious reports.

### KPI

Predicted serious percentage.

### Comparison

Actual serious classification versus predicted serious classification.

### Distribution

Distribution of `predicted_probability`.

The dashboard is intended for analytical exploration rather than clinical decision-making.

---

## 19. Data Quality and Validation

Day 6 validation covers:

### Dataset validation

* 1,000 input adverse-event reports
* 2,749 reaction records
* 3,079 drug records
* 1,000 ML feature rows
* no duplicate adverse-event IDs in the Silver event dataset
* target has no null values
* feature-level missingness is retained and handled during modelling

### Model validation

* 80/20 stratified train/test split
* 200 holdout records
* baseline model established
* classification metrics calculated
* confusion matrix calculated
* ROC-AUC calculated
* PR-AUC calculated
* feature importance generated
* SHAP analysis generated
* Isolation Forest anomaly screening completed

### Serving validation

* ML prediction Parquet written to ADLS ML layer
* Synapse Serverless reads the Parquet
* `dbo.vw_openfda_ml_predictions` exposes the model output
* Power BI can consume the Synapse serving layer

---

## 20. Automated Repository Tests

Day 6 adds:

```text
tests/test_day6_ml.py
```

The test suite validates the expected Day 6 repository structure and ML artefacts without requiring the Databricks runtime.

The tests check that:

* the ML transformation exists
* the Day 6 notebook exists
* the Day 6 documentation exists
* the ML feature dataset definition exists
* the expected ML transformation columns are present in the source code
* leakage-control fields are explicitly excluded
* the documentation contains the recorded model results
* the prediction-serving view is documented

The repository also continues to use Python compilation validation:

```bash
python -m compileall ingestion scripts transformations
```

---

## 21. Testing Limitation

The local Cloud Shell environment used for the final repository validation did not have the `pytest` executable available in the active shell session at the time of documentation.

Python source compilation completed successfully:

```text
python -m compileall ingestion scripts transformations
```

The Day 6 test file is therefore designed as a lightweight repository/artefact test and should be executed after activating the project's Python environment where `pytest` is installed.

Expected command:

```bash
pytest -q
```

or, when using the project virtual environment:

```bash
.venv/bin/pytest -q
```

---

## 22. Reproducibility

The ML workflow is version-controlled through:

```text
notebooks/Day6_OpenFDA_ML.ipynb
transformations/ml/openfda_features.py
tests/test_day6_ml.py
docs/day6-analytics-ml.md
```

The notebook records the modelling methodology and experiment outputs.

The transformation script creates the reusable ML feature dataset.

The ADLS ML layer stores the ML feature and prediction outputs used by downstream serving.

---

## 23. Important Analytical Limitations

The openFDA adverse-event reporting data has important limitations.

The records represent submitted adverse-event reports rather than a controlled clinical study population.

Therefore this project does not estimate:

* incidence rates
* relative risk
* treatment effectiveness
* population prevalence
* causal relationships between drugs and adverse reactions

Reporting volume can be affected by:

* reporting practices
* regulatory processes
* geography
* product exposure
* media attention
* changes in reporting systems
* selection bias

The ML model therefore demonstrates an engineering and analytical workflow rather than a validated clinical risk model.

The 1,000-record controlled sample is also insufficient for production deployment or claims about generalisation.

---

## 24. Engineering Outcome

Day 6 demonstrates the transition from a lakehouse data platform into an ML-enabled analytical workflow.

The completed flow is:

```text
Public data
    ↓
ADF ingestion
    ↓
ADLS RAW
    ↓
Bronze
    ↓
Silver
    ↓
ML feature engineering
    ↓
Databricks ML experimentation
    ↓
XGBoost classification
    ↓
Isolation Forest anomaly screening
    ↓
SHAP explainability
    ↓
ML predictions
    ↓
ADLS ML layer
    ↓
Synapse Serverless
    ↓
Power BI
```

The implementation demonstrates separation of:

* ingestion
* storage
* transformation
* feature engineering
* model experimentation
* model outputs
* SQL serving
* BI consumption

The Databricks Free Edition environment imposes limitations on direct external cloud-storage configuration. The project therefore uses the Databricks Unity Catalog volume for the ML experimentation environment and transfers the generated ML prediction output into the Azure ADLS ML layer for downstream Synapse and Power BI consumption. This limitation is explicitly documented rather than represented as a fully automated production Databricks integration.

---

## 25. Day 6 Completion Criteria

Day 6 is considered complete when the following are version-controlled and validated:

* [x] OpenFDA Silver datasets available
* [x] ML feature transformation implemented
* [x] ML feature dataset generated
* [x] Target and leakage controls documented
* [x] Baseline model implemented
* [x] XGBoost classifier implemented
* [x] XGBoost evaluation completed
* [x] Confusion matrix generated
* [x] Feature importance generated
* [x] SHAP analysis completed
* [x] Isolation Forest anomaly detection completed
* [x] MLflow experiment tracking attempted/completed in Databricks
* [x] ML prediction output generated
* [x] ML prediction output available in ADLS ML layer
* [x] Synapse Serverless serving view created
* [x] Power BI serving foundation established
* [x] Databricks notebook exported to GitHub
* [x] Day 6 repository test added
* [x] Python compilation validation completed
* [ ] Final pytest execution completed in the project Python environment
* [ ] Git commit and push completed

---

## 26. Day 6 Portfolio Positioning

The project should be described as:

> A cloud data engineering and analytics pipeline that ingests public-health and adverse-event data into Azure ADLS Gen2, applies medallion transformations, engineers ML features, performs supervised and unsupervised ML experimentation in Databricks, and serves ML outputs through Synapse Serverless for Power BI analytics.

The ML component demonstrates:

```text
Data engineering
      +
Machine learning
      +
Explainability
      +
Data quality
      +
SQL serving
      +
BI consumption
```

It should not be presented as a production clinical prediction system.
