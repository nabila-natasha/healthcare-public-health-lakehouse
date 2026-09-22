# Day 5 — Medallion Processing and Data Quality

## Overview

Day 5 implements the Bronze → Silver → Gold processing layer for the healthcare public-health lakehouse.

The objective is to convert the Bronze outputs from Day 3 and Day 4 into typed, validated, deduplicated, and analytics-ready datasets while preserving source lineage and enabling source-to-target reconciliation.

Python is used as the transformation compute layer, with Pandas for dataframe processing and PyArrow for Parquet output. Azure Data Lake Storage Gen2 (ADLS Gen2) remains the persistent lake storage layer.

This design is consistent with the project's Databricks Free Edition integration boundary. Databricks Free Edition is reserved for the later ML/PySpark workload rather than being used as the primary Azure ingestion or transformation engine.

---

## 1. Day 5 Objectives

The Day 5 processing layer addresses the following engineering objectives:

1. Convert Bronze records into typed Silver datasets.
2. Preserve source and ingestion lineage.
3. Deduplicate records using deterministic identifiers.
4. Validate required fields and data types.
5. Flatten nested structures where appropriate.
6. Transform Silver datasets into analytics-oriented Gold datasets.
7. Define and validate analytical grain.
8. Reconcile source records across transformation layers.
9. Establish repeatable transformation logic.
10. Produce validation evidence suitable for downstream analytics and CI/CD.
11. Store Silver and Gold datasets in an analytical columnar format.
12. Keep generated execution artifacts separate from version-controlled source code.

---

## 2. Processing Architecture

```text
                         ADLS Gen2
                            │
             ┌──────────────┴──────────────┐
             │                             │
       CDC Bronze                     openFDA Bronze
       JSON events                       CSV
             │                             │
             ▼                             ▼
       Python transform              Python transform
             │                             │
             ▼                             ▼
        CDC Silver                   openFDA Silver
        Parquet                     Parquet
             │                             │
             ▼                             ▼
       Python transform              Python transform
             │                             │
             ▼                             ▼
        CDC Gold                    openFDA Gold
        Parquet                     Parquet
             │                             │
             └──────────────┬──────────────┘
                            ▼
                    Analytics / BI / ML
```

The architecture separates:

* storage
* transformation compute
* analytical datasets
* validation

ADLS Gen2 remains the persistent storage layer.

Python performs the layer-to-layer transformation.

Parquet is used for Silver and Gold because it provides typed, columnar storage suitable for analytical workloads and future Spark/Synapse processing.

---

## 3. Medallion Layer Responsibilities

### Bronze

Bronze preserves data close to its ingestion representation.

Examples:

```text
CDC     → JSON event records
openFDA → CSV
```

Bronze supports:

* lineage
* replay
* troubleshooting
* downstream transformation
* preservation of ingestion-oriented structures

Bronze is not treated as the final analytical layer.

### Silver

Silver provides a trusted processing boundary.

Silver processing includes:

* schema standardization
* type conversion
* required-field validation
* deduplication
* flattening of nested structures where appropriate
* preservation of source lineage
* preparation for downstream analytics

### Gold

Gold provides analytics-oriented datasets.

Gold processing includes:

* aggregation
* analytical grain definition
* derived metrics
* duplicate-grain validation
* source reconciliation
* reporting-oriented measures

Gold is not necessarily one-to-one with Silver. Row counts may change when aggregation is performed.

---

# 4. CDC Processing

## 4.1 CDC Source

The CDC dataset used in the project is:

**Weekly United States COVID-19 Cases and Deaths by State — ARCHIVED**

Dataset ID:

```text
pwn4-m3yp
```

The dataset was historically replayed through the Day 4 Event Hubs streaming architecture.

It is therefore important to describe this as a **historical replay through a streaming architecture**, rather than a live CDC source.

The dataset contains state-level COVID-19 reporting information, including:

```text
date_updated
state
start_date
end_date
tot_cases
new_cases
tot_deaths
new_deaths
new_historic_cases
new_historic_deaths
```

---

## 4.2 CDC Bronze Input

CDC Bronze records are stored under:

```text
healthcare/bronze/cdc/day4_final_20260921/
```

The final ingestion partition is:

```text
ingestion_date=2026-09-21/
```

Each Bronze record contains an event envelope:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
processed_time
```

The nested payload contains the original CDC fields:

```text
date_updated
state
start_date
end_date
tot_cases
new_cases
tot_deaths
new_deaths
new_historic_cases
new_historic_deaths
```

The Bronze layer therefore retains both the source event information and the platform processing information.

---

## 4.3 CDC Bronze → Silver

The CDC Bronze → Silver transformation is implemented in:

```text
transformations/silver/cdc_bronze_to_silver.py
```

The transformation:

1. Recursively discovers Bronze JSON files.
2. Reads the event envelope.
3. Extracts the CDC payload.
4. Flattens the payload into analytical columns.
5. Converts timestamps into typed UTC timestamps.
6. Converts reporting dates into date values.
7. Converts CDC numerical measures into numeric values.
8. Deduplicates using `event_id`.
9. Validates required fields.
10. Writes the resulting dataset as Parquet.

The local transformation output is:

```text
tmp/day5/cdc_silver/cdc_silver.parquet
```

The validated ADLS output is:

```text
healthcare/silver/cdc/cdc_silver.parquet
```

---

## 4.4 CDC Silver Schema

The CDC Silver dataset contains 15 columns:

```text
event_id
event_time
ingestion_time
processed_time
source
source_dataset_id
state
start_date
end_date
tot_cases
new_cases
tot_deaths
new_deaths
new_historic_cases
new_historic_deaths
```

The lineage columns are intentionally retained:

```text
event_id
event_time
ingestion_time
processed_time
source
source_dataset_id
```

This allows downstream processing to distinguish source event time from platform processing time.

---

## 4.5 Event Time vs Ingestion Time

The CDC data is historical data replayed through Event Hubs.

Therefore:

```text
event_time
```

represents the source/update time carried by the event.

Whereas:

```text
ingestion_time
```

represents the time the platform received the event.

For example:

```text
event_time     = historical source date
ingestion_time = 2026-09-21
```

This difference is expected because the source records are historical.

Preserving both timestamps provides a foundation for:

* event-time analysis
* ingestion-latency analysis
* replay diagnostics
* late-event detection
* future streaming implementations

During Day 4, late-event detection was performed by the streaming consumer using event time. The late status was logged for operational diagnostics and was **not persisted as a Bronze data-quality field**.

---

## 4.6 CDC Deduplication

The Day 4 producer generates a deterministic `event_id` from the source record identity.

The Silver transformation uses:

```text
event_id
```

as the deduplication key.

This prevents duplicate deliveries from creating duplicate analytical records.

Final Silver validation:

```text
CDC Silver rows      : 1000
Duplicate event IDs  : 0
```

Result:

```text
CDC Silver: PASS
```

The deduplication performed here is a second analytical safeguard after the Day 4 streaming consumer's duplicate-delivery handling.

---

## 4.7 CDC Silver → Gold

The CDC Silver dataset is transformed into a Gold analytical representation.

The transformation is implemented in:

```text
transformations/gold/cdc_silver_to_gold.py
```

The local output is:

```text
tmp/day5/cdc_gold/cdc_gold.parquet
```

The validated ADLS output is:

```text
healthcare/gold/cdc/cdc_gold.parquet
```

---

## 4.8 CDC Gold Grain

The CDC Gold grain is:

> One row per state and reporting period.

The grain is defined by:

```text
state
start_date
end_date
```

The resulting Gold columns are:

```text
state
start_date
end_date
total_cases
new_cases
total_deaths
new_deaths
historic_cases
historic_deaths
source_event_count
cumulative_death_case_ratio_pct
```

The Gold layer therefore provides an analytical representation rather than simply copying every Silver column.

---

## 4.9 CDC Gold Measures

The CDC Gold dataset contains the following measures:

```text
total_cases
new_cases
total_deaths
new_deaths
historic_cases
historic_deaths
source_event_count
cumulative_death_case_ratio_pct
```

The original CDC numerical measures are renamed into clearer analytical names where appropriate.

For example:

```text
tot_cases  → total_cases
tot_deaths → total_deaths
```

`source_event_count` is included as a reconciliation measure.

It represents the number of Silver source events contributing to each Gold record.

---

## 4.10 Cumulative Death-to-Case Ratio

The CDC Gold transformation derives:

```text
cumulative_death_case_ratio_pct
```

using:

```text
total_deaths
---------------- × 100
total_cases
```

Operationally:

```python
(total_deaths / total_cases) * 100
```

This metric is a **portfolio-derived analytical ratio**.

It is not presented as an official CDC case-fatality measure.

The metric is intended to provide a simple analytical comparison between cumulative reported deaths and cumulative reported cases in the source data.

### Zero denominator handling

If:

```text
total_cases = 0
```

the ratio is not mathematically defined.

The transformation therefore does not force the result to `0`.

Instead, the result remains undefined/NaN for those records.

During Day 5 validation, this resulted in some Gold rows having an undefined ratio because both numerator and denominator were zero.

This behavior is intentional because:

```text
0 deaths / 0 cases
```

does not provide a meaningful percentage.

Therefore, the ratio is **not required to be non-null** in the validation framework.

---

## 4.11 CDC Gold Validation

The CDC Gold validation reported:

```text
Rows             : 1000
Columns          : 11
States           : 60
Duplicate grain  : 0
```

The Gold grain:

```text
state + start_date + end_date
```

contained no duplicates.

Result:

```text
CDC Gold: PASS
```

---

## 4.12 CDC Reconciliation

The CDC Silver and Gold datasets were reconciled using:

```text
source_event_count
```

The validation reported:

```text
Silver source events : 1000
Gold source events   : 1000
```

The reconciliation therefore passed:

```text
CDC reconciliation: PASS
```

This provides evidence that all validated Silver source events remained represented in the Gold dataset.

The reconciliation is particularly important because a transformation completing without an exception does not by itself prove that records were not lost.

---

# 5. openFDA Processing

## 5.1 openFDA Source

The openFDA adverse-event dataset was ingested during Day 3 using Azure Data Factory.

The Day 3 controlled dataset contains:

```text
100 adverse-event reports
```

The source contains report-level information together with nested reaction and drug information.

---

## 5.2 openFDA Bronze Input

The Bronze dataset is:

```text
healthcare/bronze/openfda/openfda_adverse_events.csv
```

The principal fields include:

```text
safetyreportid
transmissiondate
receivedate
receiptdate
serious
seriousnessdeath
fulfillexpeditecriteria
companynumb
reportercountry
reporterqualification
senderorganization
patientonsetage
patientonsetageunit
patientsex
patientdeathdate
reactions_json
drugs_json
```

---

## 5.3 openFDA Bronze → Silver

The openFDA Bronze → Silver transformation is implemented in:

```text
transformations/silver/openfda_bronze_to_silver.py
```

The transformation processes:

* report-level fields
* report identifiers
* date fields
* categorical fields
* patient attributes
* nested reaction records
* nested drug records

The nested JSON structures are parsed into separate analytical datasets.

Three Silver Parquet datasets are produced:

```text
adverse_events.parquet
adverse_event_reactions.parquet
adverse_event_drugs.parquet
```

The validated ADLS locations are:

```text
healthcare/silver/openfda/adverse_events.parquet
healthcare/silver/openfda/adverse_event_reactions.parquet
healthcare/silver/openfda/adverse_event_drugs.parquet
```

---

## 5.4 openFDA Silver Parent Dataset

The parent Silver dataset is:

```text
adverse_events
```

Its grain is:

> One row per adverse-event report.

The primary report-level identifier is:

```text
safetyreportid
```

The dataset contains:

```text
100
```

unique adverse-event reports.

---

## 5.5 openFDA Reaction Dataset

The reaction child dataset is:

```text
adverse_event_reactions
```

Its grain is:

> One row per reaction associated with an adverse-event report.

The Day 5 transformation produced:

```text
247 reaction records
```

The higher row count is expected because one adverse-event report can contain multiple reaction records.

The relationship is therefore:

```text
adverse_events
       │
       └──< adverse_event_reactions
```

---

## 5.6 openFDA Drug Dataset

The drug child dataset is:

```text
adverse_event_drugs
```

Its grain is:

> One row per drug associated with an adverse-event report.

The Day 5 transformation produced:

```text
265 drug records
```

The higher row count is expected because one adverse-event report can contain multiple drug records.

The relationship is:

```text
adverse_events
       │
       └──< adverse_event_drugs
```

Separating the nested arrays into child datasets avoids repeatedly parsing nested JSON structures during downstream analytics.

---

## 5.7 openFDA Silver Validation

The Day 5 validation reported:

```text
Adverse events       : 100
Reaction records     : 247
Drug records         : 265
Duplicate report IDs : 0
```

The difference between report count and reaction/drug counts is expected because a single adverse-event report may contain multiple reactions and multiple drugs.

The primary report-level identifier is:

```text
safetyreportid
```

No duplicate report IDs remained after Silver processing.

Result:

```text
openFDA Silver: PASS
```

---

# 6. Gold Processing

Gold datasets are designed for analytical consumption rather than one-to-one preservation of Silver rows.

Therefore Gold row counts are not expected to equal Silver row counts in every dataset.

The key controls are:

* expected output
* expected schema
* analytical grain
* duplicate grain
* derived metrics
* source reconciliation

---

## 6.1 CDC Gold

The CDC Gold transformation is implemented in:

```text
transformations/gold/cdc_silver_to_gold.py
```

The analytical grain is:

```text
state
start_date
end_date
```

Validation:

```text
Rows             : 1000
Columns          : 11
States           : 60
Duplicate grain  : 0
```

CDC reconciliation:

```text
Silver source events : 1000
Gold source events   : 1000
```

Result:

```text
CDC reconciliation: PASS
CDC Gold: PASS
```

---

## 6.2 openFDA Gold

The openFDA Gold transformation is implemented in:

```text
transformations/gold/openfda_silver_to_gold.py
```

The local output is:

```text
tmp/day5/openfda_gold/openfda_gold.parquet
```

The validated ADLS output is:

```text
healthcare/gold/openfda/openfda_gold.parquet
```

The Gold grain is:

> One row per reporter country and transmission date.

The grouping dimensions are:

```text
reporter_country
transmission_date
```

The resulting columns are:

```text
reporter_country
transmission_date
adverse_event_reports
serious_reports
death_reports
expedited_reports
serious_report_pct
death_report_pct
expedited_report_pct
```

---

## 6.3 openFDA Gold Measures

The openFDA Gold dataset provides:

```text
adverse_event_reports
serious_reports
death_reports
expedited_reports
```

and corresponding percentages:

```text
serious_report_pct
death_report_pct
expedited_report_pct
```

The percentages are derived from the Gold report counts.

For example:

```text
serious_report_pct
    =
serious_reports / adverse_event_reports × 100
```

Similarly:

```text
death_report_pct
    =
death_reports / adverse_event_reports × 100
```

and:

```text
expedited_report_pct
    =
expedited_reports / adverse_event_reports × 100
```

These are derived portfolio reporting metrics and should not be interpreted as official FDA rates unless separately defined and validated against the appropriate regulatory methodology.

---

## 6.4 openFDA Gold Validation

Validation:

```text
Rows             : 15
Columns          : 9
Countries        : 11
Duplicate grain  : 0
```

The Gold dataset contains fewer rows than the 100 Silver reports because the Gold layer aggregates reports by:

```text
reporter_country
transmission_date
```

This is expected aggregation rather than record loss.

---

## 6.5 openFDA Reconciliation

The openFDA Gold dataset includes:

```text
adverse_event_reports
```

which is used to reconcile the Gold aggregate back to the Silver parent dataset.

Validation:

```text
Silver report IDs : 100
Gold report count : 100
```

Result:

```text
openFDA reconciliation: PASS
openFDA Gold: PASS
```

This confirms that the 100 unique Silver report IDs remain represented in the Gold aggregation.

---

# 7. Data Quality Controls

The Day 5 validation framework covers several data-quality dimensions.

## Completeness

Checks whether expected records remain represented after transformation.

Examples:

```text
CDC Silver source events = CDC Gold source events

openFDA Silver report IDs = openFDA Gold report count
```

---

## Uniqueness

Uniqueness is validated at the appropriate grain.

CDC:

```text
event_id
```

openFDA:

```text
safetyreportid
```

Gold datasets use their defined analytical grain.

CDC Gold:

```text
state + start_date + end_date
```

openFDA Gold:

```text
reporter_country + transmission_date
```

---

## Validity

Silver processing converts source values into appropriate analytical types.

Examples include:

```text
timestamps
dates
numeric measures
categorical values
```

Required fields are also validated.

---

## Referential / Structural Integrity

The openFDA parent-child model is checked through the report-level identifier:

```text
safetyreportid
```

This provides a structural relationship between:

```text
adverse_events
adverse_event_reactions
adverse_event_drugs
```

---

## Reconciliation

Reconciliation compares source-level records across transformation boundaries.

This provides stronger evidence than simply checking whether a transformation script completed successfully.

---

# 8. Hard Validation vs Diagnostic Checks

The project distinguishes between hard validation failures and diagnostic observations.

## Hard validation

A hard validation condition prevents a record or dataset from being accepted.

Examples:

* missing required event identity
* missing required timestamp
* malformed event envelope
* missing required report ID
* duplicate identity where uniqueness is mandatory
* missing expected output
* duplicate Gold grain

## Diagnostic / Informational Validation

A diagnostic condition should be investigated but should not automatically invalidate the dataset without domain justification.

Examples:

* unusual statistical distributions
* historical reporting revisions
* changes in source reporting patterns
* statistical outliers
* undefined derived ratios caused by zero denominators

This distinction avoids embedding unsupported business assumptions into the data pipeline.

---

# 9. CDC Domain Considerations

CDC aggregate data can be retrospectively updated by the source.

Therefore, simple rules such as:

```text
new_cases <= total_cases
```

should not automatically be treated as hard data-quality failures without confirming the source's reporting semantics.

Historical corrections and reporting revisions can affect aggregate relationships.

The Day 5 validation therefore emphasizes:

* structural validity
* typing
* identity
* completeness
* reconciliation

rather than imposing unsupported domain constraints.

The derived:

```text
cumulative_death_case_ratio_pct
```

is also treated as an analytical portfolio metric rather than an official CDC measure.

---

# 10. Quarantine and Invalid Records

The Day 4 streaming consumer does not silently discard malformed events.

Invalid events are routed to:

```text
healthcare/quarantine/cdc/
```

The final Day 4 validation contained:

```text
1 quarantined malformed event
```

The recorded reason was:

```text
Missing event fields: event_time
```

This allows invalid input to be investigated separately without contaminating the trusted Bronze layer.

The Day 4 final ADLS reconciliation was:

```text
RAW files         : 1002
Bronze files      : 1000
Quarantine files  : 1
```

The difference between RAW and Bronze reflects duplicate/malformed event handling during the streaming process.

---

# 11. Idempotency

The transformation layer is designed around deterministic record identities.

CDC:

```text
event_id
```

openFDA:

```text
safetyreportid
```

These identifiers support duplicate detection during repeated processing.

The intended behavior is:

```text
same Bronze input
        │
        ▼
same transformation
        │
        ▼
same Silver/Gold logical result
```

rather than accumulating duplicate analytical records.

The transformation code itself is version-controlled, while generated Parquet execution artifacts are kept outside Git.

---

# 12. Storage Format

The project intentionally uses different formats at different stages.

```text
CDC Bronze     → JSON
openFDA Bronze → CSV

CDC Silver     → Parquet
openFDA Silver → Parquet

CDC Gold       → Parquet
openFDA Gold   → Parquet
```

Parquet is used for Silver and Gold because it provides:

* typed columns
* columnar storage
* compression
* efficient analytical reads
* compatibility with Spark
* compatibility with downstream Azure analytics services
* a clean boundary between ingestion-oriented Bronze data and analytical datasets

---

# 13. Compute and Storage Separation

The transformation architecture intentionally distinguishes compute from storage.

```text
ADLS Gen2 = storage
Python    = transformation compute
Parquet   = analytical storage format
```

The transformation logic does not execute "inside ADLS."

Instead:

```text
ADLS Bronze
     │
     ▼
Python transformation
     │
     ▼
ADLS Silver
     │
     ▼
Python transformation
     │
     ▼
ADLS Gold
```

This separation provides a clear architecture boundary and allows the compute technology to evolve independently from the storage layer.

---

# 14. Databricks Boundary

Databricks Free Edition is not used as the primary Day 5 transformation engine.

The project's ADR defines Databricks Free Edition as a separate ML/PySpark execution environment.

The primary Azure data path remains:

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
      ▼
 ML-ready dataset
      │
      ▼
Databricks Free Edition
```

A future production implementation could replace the Python transformation layer with Spark/Databricks processing where scale and operational requirements justify it.

The current implementation deliberately avoids introducing Azure Databricks solely to demonstrate a technology when the portfolio dataset does not require distributed processing.

---

# 15. ADLS Output Layout

The Day 5 outputs are stored in ADLS as follows:

```text
healthcare/
|
+-- silver/
|   |
|   +-- cdc/
|   |   `-- cdc_silver.parquet
|   |
|   `-- openfda/
|       +-- adverse_events.parquet
|       +-- adverse_event_reactions.parquet
|       `-- adverse_event_drugs.parquet
|
`-- gold/
    |
    +-- cdc/
    |   `-- cdc_gold.parquet
    |
    `-- openfda/
        `-- openfda_gold.parquet
```

The uploaded outputs were:

```text
silver/cdc/cdc_silver.parquet
silver/openfda/adverse_events.parquet
silver/openfda/adverse_event_reactions.parquet
silver/openfda/adverse_event_drugs.parquet
gold/cdc/cdc_gold.parquet
gold/openfda/openfda_gold.parquet
```

---

# 16. Validation Script

The Day 5 manual/cloud validation is implemented in:

```text
scripts/silver_gold_validations.py
```

The script validates the actual generated Day 5 Parquet outputs.

The validation checks:

* expected Parquet files exist
* CDC Silver row count
* CDC Silver column count
* CDC state coverage
* CDC duplicate event IDs
* CDC required fields
* CDC Gold row count
* CDC Gold column count
* CDC Gold state coverage
* CDC Gold duplicate grain
* CDC Silver-to-Gold reconciliation
* openFDA Silver report count
* openFDA reaction count
* openFDA drug count
* openFDA duplicate report IDs
* openFDA Gold row count
* openFDA Gold column count
* openFDA country coverage
* openFDA Gold duplicate grain
* openFDA Silver-to-Gold reconciliation

This script is intended for **manual/cloud validation of the generated Day 5 outputs**.

It is different from the repository's CI tests.

---

# 17. Test Strategy

The project separates runtime data validation from CI-safe source validation.

## Manual / Cloud Validation

The script:

```text
scripts/silver_gold_validations.py
```

validates the actual generated Day 5 datasets.

It is run against local transformation outputs such as:

```text
tmp/day5/
```

after the Bronze-to-Silver and Silver-to-Gold processing has completed.

This provides evidence that the actual transformation run produced the expected results.

## CI Validation

GitHub CI validates source code and repository structure without requiring access to the Azure subscription or generated `tmp/` datasets.

This distinction is intentional.

The project does not commit generated Parquet outputs simply to make CI pass.

Instead:

```text
GitHub repository
    │
    ├── transformation source code
    ├── validation source code
    ├── tests
    └── documentation
```

while:

```text
Local / Cloud execution
    │
    └── tmp/day5/
          └── generated Parquet outputs
```

This keeps the Git repository focused on reproducible source code rather than execution artifacts.

---

# 18. Reproducibility

The transformation logic is stored in GitHub:

```text
transformations/silver/
transformations/gold/
scripts/silver_gold_validations.py
```

The transformation inputs are defined by the Day 3 and Day 4 Bronze outputs.

The processing sequence is:

```text
Bronze
   │
   ▼
Silver transformation
   │
   ▼
Silver validation
   │
   ▼
Gold transformation
   │
   ▼
Gold validation
   │
   ▼
Source reconciliation
```

The same transformation code can therefore be rerun against the same controlled Bronze inputs for troubleshooting or validation.

---

# 19. Generated Artifacts and Git

Generated transformation outputs are stored under:

```text
tmp/
```

The repository `.gitignore` excludes:

```text
tmp/
```

This prevents generated Parquet files and other local execution artifacts from being committed.

The repository should contain the transformation logic and validation logic, not the temporary execution outputs.

The Python virtual environment is also not intended to be committed.

---

# 20. CI/CD Boundary

The Day 5 implementation is designed so that GitHub CI does not depend on an active Azure subscription.

GitHub CI validates:

* Python dependencies
* Python syntax
* transformation source files
* repository tests
* required documentation

The actual Azure-generated datasets are validated separately because generated `tmp/` artifacts are intentionally excluded from Git.

Therefore:

```text
GitHub CI
    │
    ├── source validation
    ├── Python compilation
    ├── repository tests
    └── documentation checks
```

can continue to run even if the Azure trial subscription later expires.

The CD workflow is different because an actual Azure deployment/environment validation requires Azure authentication and an active Azure environment.

Therefore:

```text
GitHub CD
    │
    └── Azure-dependent release/deployment validation
```

The workflow files remain in GitHub even if the Azure trial later expires.

This separation prevents the CI pipeline from becoming dependent on a temporary cloud subscription.

---

# 21. Engineering Decisions

## Python/Pandas instead of Azure Databricks

The transformation layer uses Python/Pandas because the project is operating under Azure trial and cost constraints.

The datasets used for this portfolio project are small enough for this execution model.

Databricks Free Edition is retained as a separate environment for PySpark and ML experimentation.

---

## Parquet instead of CSV for Silver/Gold

Parquet provides stronger analytical characteristics than CSV, including:

* typed columns
* compression
* columnar storage
* analytical read efficiency
* compatibility with Spark-based processing

---

## Separate parent and child openFDA tables

Nested reactions and drugs are normalized into child datasets to preserve their one-to-many relationships and avoid repeatedly parsing nested structures during analytics.

---

## Reconciliation before analytics

The pipeline validates source-to-target representation before treating the Gold outputs as analytics-ready.

This reduces the risk of silent data loss during transformation.

---

## Explicit analytical grain

Gold datasets define their intended grain before analytical use.

CDC:

```text
state + start_date + end_date
```

openFDA:

```text
reporter_country + transmission_date
```

Grain validation is then performed against these definitions.

---

## Derived metrics are explicitly labelled

The CDC:

```text
cumulative_death_case_ratio_pct
```

and openFDA percentage metrics are explicitly treated as derived portfolio metrics.

This prevents derived calculations from being mistaken for official source-provided measures.

---

# 22. Final Day 5 Validation Evidence

The final validation result was:

```text
========================================================================
SILVER / GOLD VALIDATION
========================================================================

All expected Parquet files found.

===== CDC SILVER =====
Rows: 1000
Columns: 15
States: 60
Duplicate event IDs: 0
CDC Silver: PASS

===== CDC GOLD =====
Rows: 1000
Columns: 11
States: 60
Duplicate grain: 0

===== CDC RECONCILIATION =====
Silver source events: 1000
Gold source events: 1000
CDC reconciliation: PASS
CDC Gold: PASS

===== OPENFDA SILVER =====
Adverse events: 100
Reaction records: 247
Drug records: 265
Duplicate report IDs: 0
openFDA Silver: PASS

===== OPENFDA GOLD =====
Rows: 15
Columns: 9
Countries: 11
Duplicate grain: 0

===== OPENFDA RECONCILIATION =====
Silver report IDs: 100
Gold report count: 100
openFDA reconciliation: PASS
openFDA Gold: PASS

========================================================================
SILVER / GOLD VALIDATION: PASS
========================================================================
```

---

# 23. Day 5 Completion

Day 5 completed the following:

* [x] CDC Bronze transformed to Silver
* [x] openFDA Bronze transformed to Silver
* [x] CDC Silver transformed to Gold
* [x] openFDA Silver transformed to Gold
* [x] Silver datasets written as Parquet
* [x] Gold datasets written as Parquet
* [x] CDC deterministic event-ID deduplication
* [x] CDC Gold grain validation
* [x] CDC source-to-Gold reconciliation
* [x] CDC derived cumulative death-to-case ratio
* [x] openFDA nested reaction flattening
* [x] openFDA nested drug flattening
* [x] openFDA report-ID validation
* [x] openFDA Gold analytical aggregation
* [x] openFDA Gold grain validation
* [x] openFDA source-to-Gold reconciliation
* [x] Day 5 validation script created
* [x] Generated transformation artifacts excluded from Git
* [x] CI-safe validation separated from runtime data validation
* [x] Day 5 processing documented

---

# 24. Engineering Outcome

At the end of Day 5, the project has moved beyond ingestion into a structured and validated transformation architecture:

```text
RAW
 |
 v
BRONZE
 |
 |  schema / identity validation
 v
SILVER
 |
 |  grain / reconciliation / derived metrics
 v
GOLD
 |
 v
Analytics / BI / ML
```

The key engineering principle is that each layer has a defined purpose:

```text
Bronze
  = ingestion-oriented preservation

Silver
  = cleaned, typed, structured, trusted data

Gold
  = business-oriented analytical datasets
```

The project now has a reproducible Bronze → Silver → Gold processing path that can support the downstream Synapse, Power BI, and ML stages.

The implementation also demonstrates an important production engineering principle:

> Transformation success is not treated as equivalent to data-quality success.

The Day 5 pipeline therefore validates schema, identity, uniqueness, analytical grain, completeness, and source-to-target reconciliation before considering the resulting datasets analytics-ready.
