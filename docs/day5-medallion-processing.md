# Day 5 — Medallion Processing and Data Quality

## Overview

Day 5 implements the Bronze → Silver → Gold processing layer for the healthcare public-health lakehouse.

The objective is to convert the Bronze outputs from Day 3 and Day 4 into typed, validated, deduplicated, and analytics-ready datasets while preserving source lineage.

Python is used as the transformation compute layer, while Azure Data Lake Storage Gen2 (ADLS Gen2) remains the persistent lake storage layer.

This design is consistent with the project's Databricks Free Edition integration boundary. Databricks Free Edition is reserved for the later ML workload rather than being used as the primary Azure ingestion or transformation engine.

---

## 1. Day 5 Objectives

The Day 5 processing layer addresses the following engineering objectives:

1. Convert Bronze records into typed Silver datasets.
2. Preserve source and ingestion lineage.
3. Deduplicate records using deterministic identifiers.
4. Validate required fields and data types.
5. Transform Silver datasets into analytics-oriented Gold datasets.
6. Reconcile source records across transformation layers.
7. Validate Gold grain and uniqueness.
8. Establish repeatable transformation logic.
9. Produce validation evidence suitable for downstream analytics and CI/CD.

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

### Silver

Silver provides a trusted processing boundary.

Silver processing includes:

* schema standardization
* type conversion
* required-field validation
* deduplication
* flattening of nested structures where appropriate
* preservation of source lineage

### Gold

Gold provides analytics-oriented datasets.

Gold processing includes:

* aggregation
* analytical grain definition
* duplicate-grain validation
* source reconciliation

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

It is therefore important to describe this as a historical replay rather than a live CDC source.

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

The payload contains:

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

## 4.3 CDC Bronze → Silver

The CDC Bronze → Silver transformation:

1. Reads Bronze JSON records.
2. Extracts the event envelope.
3. Flattens the CDC payload.
4. Converts timestamps into typed timestamp values.
5. Converts reporting dates into date values.
6. Converts CDC numerical measures into numeric values.
7. Deduplicates using `event_id`.
8. Validates required fields.
9. Writes the Silver dataset as Parquet.

The transformation script is:

```text
transformations/silver/cdc_bronze_to_silver.py
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
event_time     = 2020-04-23
ingestion_time = 2026-09-21
```

This difference is expected because the source records are historical.

Preserving both timestamps provides a foundation for:

* event-time analysis
* ingestion-latency analysis
* replay diagnostics
* late-event detection
* future streaming implementations

---

## 4.6 CDC Deduplication

The Day 4 producer generates a deterministic `event_id` from the source record identity.

The Silver transformation uses:

```text
event_id
```

as the deduplication key.

This prevents duplicate deliveries from creating duplicate analytical records.

Final validation:

```text
CDC Silver rows      : 1000
Duplicate event IDs  : 0
```

Result:

```text
CDC Silver: PASS
```

---

## 4.7 CDC Silver → Gold

The CDC Silver dataset is transformed into a Gold analytical representation.

The resulting Gold validation reported:

```text
Rows             : 1000
Columns          : 11
States           : 60
Duplicate grain  : 0
```

The Gold layer therefore passed its analytical-grain uniqueness check.

---

## 4.8 CDC Reconciliation

The CDC Silver and Gold datasets were reconciled.

```text
Silver source events : 1000
Gold source events   : 1000
```

Result:

```text
CDC reconciliation: PASS
CDC Gold: PASS
```

This provides evidence that the validated Silver source events remained represented in the Gold dataset.

---

# 5. openFDA Processing

## 5.1 openFDA Source

The openFDA adverse-event dataset was ingested during Day 3 using Azure Data Factory.

The Day 3 controlled dataset contains 100 adverse-event reports.

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

The openFDA Bronze → Silver transformation processes:

* report-level fields
* report identifiers
* date fields
* categorical fields
* patient attributes
* nested reaction records
* nested drug records

The nested JSON structures are parsed so that reaction and drug records can be validated and used downstream.

The transformation produces the openFDA Silver analytical representation.

---

## 5.4 openFDA Silver Validation

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
* source reconciliation

---

## 6.1 CDC Gold

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
CDC Gold: PASS
```

---

## 6.2 openFDA Gold

Validation:

```text
Rows             : 15
Columns          : 9
Countries        : 11
Duplicate grain  : 0
```

The Gold dataset contains fewer rows than the 100 Silver reports because Gold represents an aggregated analytical dataset.

openFDA reconciliation:

```text
Silver report IDs : 100
Gold report count : 100
```

Result:

```text
openFDA Gold: PASS
```

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

---

## Validity

Silver processing converts source values into appropriate analytical types.

Examples include:

```text
timestamps
dates
numeric measures
```

Required fields are also validated.

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

## Diagnostic / Informational Validation

A diagnostic condition should be investigated but should not automatically invalidate the dataset without domain justification.

Examples:

* unusual statistical distributions
* historical reporting revisions
* changes in source reporting patterns
* statistical outliers

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

---

# 10. Quarantine and Invalid Records

The Day 4 streaming consumer does not silently discard malformed events.

Invalid events are routed to:

```text
healthcare/quarantine/cdc/
```

The final validation contained:

```text
1 quarantined malformed event
```

The recorded reason was:

```text
Missing event fields: event_time
```

This allows invalid input to be investigated separately without contaminating the trusted Bronze layer.

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

---

# 15. Validation Script

The Day 5 validation is implemented in:

```text
scripts/silver_gold_validations.py
```

The validation checks:

* expected Parquet files exist
* CDC Silver row count
* CDC Silver column count
* CDC state coverage
* CDC duplicate event IDs
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

---

# 16. Final Day 5 Validation Evidence

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

# 17. Test Strategy

The project uses controlled datasets and repeatable validation where practical.

This provides:

* deterministic test inputs
* repeatable validation
* reduced dependency on external API availability
* safer development
* easier CI/CD testing

Live Azure resources are validated separately when the objective is to demonstrate Azure integration.

The project does not treat successful connectivity to an external service as proof of data quality.

---

# 18. Operational Considerations

The current Day 5 implementation focuses on establishing and validating the medallion processing pattern before adding additional orchestration complexity.

Future execution can be orchestrated through Azure services:

```text
Trigger
   │
   ▼
Bronze available
   │
   ▼
Transformation
   │
   ▼
Silver
   │
   ▼
Gold
   │
   ▼
Data-quality validation
   │
   ▼
Analytics / ML
```

For the current portfolio implementation, transformation correctness is established before introducing additional orchestration layers.

---

# 19. Engineering Practices Demonstrated

Day 5 demonstrates:

* Bronze → Silver processing
* Silver → Gold processing
* schema enforcement
* type conversion
* JSON flattening
* nested JSON processing
* deterministic deduplication
* lineage preservation
* data-quality validation
* source-to-Gold reconciliation
* analytical aggregation
* Parquet-based analytical storage
* separation of compute and storage
* repeatable transformation logic
* explicit documentation of limitations

---

# 20. Day 5 Outcome

The Day 5 medallion processing layer successfully passed all implemented Silver/Gold validation controls.

### CDC

```text
Bronze → Silver → Gold

Silver rows          : 1000
States               : 60
Duplicate event IDs  : 0
Source events        : 1000
Gold source events   : 1000
Duplicate Gold grain : 0
```

### openFDA

```text
Bronze → Silver → Gold

Adverse-event reports : 100
Reaction records      : 247
Drug records          : 265
Duplicate report IDs  : 0
Gold rows             : 15
Countries             : 11
Duplicate Gold grain  : 0
```

### Overall

```text
SILVER / GOLD VALIDATION: PASS
```

The lakehouse now has a validated Bronze → Silver → Gold processing path ready for the downstream Synapse, Power BI, and ML stages.
