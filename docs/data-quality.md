# Data Quality Framework

## Purpose

Data quality is treated as an engineering control throughout the healthcare public-health lakehouse rather than as a final dashboard check.

The project applies validation at multiple stages:

```text
Source
  │
  ▼
RAW
  │
  ▼
Bronze
  │
  ├── schema / completeness / malformed-record checks
  │
  ▼
Silver
  │
  ├── typing / validity / uniqueness / required fields
  │
  ▼
Gold
  │
  ├── grain / reconciliation / aggregation checks
  │
  ▼
Analytics / ML
```

The controls are designed to detect data loss, duplication, malformed records, invalid values, and transformation inconsistencies.

---

# 1. Data Quality Principles

The project follows these principles:

1. Validate as early as practical.
2. Do not silently discard malformed records.
3. Preserve source lineage.
4. Use deterministic identifiers where possible.
5. Validate uniqueness at the correct grain.
6. Reconcile records across transformation boundaries.
7. Separate hard validation failures from informational diagnostics.
8. Keep Bronze available for investigation and replay.
9. Use controlled fixtures for repeatable tests.
10. Do not claim successful validation without evidence.

---

# 2. RAW Layer

RAW preserves the source representation as received.

Controls include:

* successful source retrieval
* expected file existence
* file-size sanity checks
* source response validation
* preservation of the original structure

RAW is not treated as fully trusted analytical data.

It provides the replay and lineage boundary for downstream processing.

---

# 3. Bronze Layer

Bronze focuses on ingestion integrity.

## 3.1 CDC Bronze

The Day 4 CDC streaming pipeline validates:

* required event fields
* event identity
* event timestamp
* ingestion timestamp
* source metadata
* malformed event handling
* duplicate delivery detection

The event envelope contains:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

A deliberately malformed event missing `event_time` was routed to quarantine.

Final Day 4 validation:

```text
RAW files        : 1002
Bronze files     : 1000
Quarantine files : 1
```

This demonstrates that malformed input was not allowed to enter Bronze as a normal analytical record.

---

## 3.2 openFDA Bronze

The Day 3 batch pipeline validates:

* successful REST retrieval
* expected source response structure
* presence of adverse-event records
* required `safetyreportid`
* duplicate report IDs
* successful Bronze CSV creation

The Bronze transformation preserves selected nested reaction and drug structures as JSON strings.

---

# 4. Silver Layer

Silver is the primary data-standardization layer.

Controls include:

* schema validation
* required-field validation
* timestamp parsing
* date parsing
* numeric type conversion
* duplicate detection
* source lineage preservation
* structured nested-data processing

---

# 5. CDC Silver Controls

The CDC Bronze → Silver transformation produces 15 columns:

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

## 5.1 Required Fields

The following fields must be present:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
state
start_date
end_date
```

Records failing required-field validation are not accepted as valid Silver records.

---

## 5.2 Numeric Validity

CDC numeric measures are converted from their Bronze string representation into numeric values.

Examples:

```text
tot_cases
new_cases
tot_deaths
new_deaths
new_historic_cases
new_historic_deaths
```

The transformation uses numeric parsing rather than treating these fields as free-form text.

---

## 5.3 Timestamp Validity

The transformation parses:

```text
event_time
ingestion_time
processed_time
```

as timestamps.

This supports downstream time-based analysis and preserves the distinction between source event time and platform processing time.

---

## 5.4 Deduplication

CDC records use:

```text
event_id
```

as the deterministic identity.

Final Day 5 validation:

```text
CDC Silver rows      : 1000
Duplicate event IDs  : 0
```

Result:

```text
CDC Silver: PASS
```

---

# 6. openFDA Silver Controls

The openFDA Silver layer validates the report-level identity:

```text
safetyreportid
```

Final Day 5 validation:

```text
Adverse events       : 100
Reaction records     : 247
Drug records         : 265
Duplicate report IDs : 0
```

The nested reaction and drug structures are processed from:

```text
reactions_json
drugs_json
```

The reaction and drug counts can exceed the number of adverse-event reports because one report can contain multiple reaction and drug records.

---

# 7. Gold Layer

Gold validation focuses on analytical usability.

Controls include:

* expected output existence
* expected schema
* correct analytical grain
* duplicate-grain detection
* source reconciliation
* aggregation consistency

Gold is not expected to have the same row count as Silver because Gold can contain aggregated records.

---

# 8. CDC Gold Controls

Final validation:

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

# 9. openFDA Gold Controls

Final validation:

```text
Rows             : 15
Columns          : 9
Countries        : 11
Duplicate grain  : 0
```

The smaller row count is expected because Gold represents an aggregated analytical view of the 100 report-level Silver records.

openFDA reconciliation:

```text
Silver report IDs : 100
Gold report count : 100
```

Result:

```text
openFDA reconciliation: PASS
openFDA Gold: PASS
```

---

# 10. Reconciliation Controls

Reconciliation is used to detect silent record loss or unexpected duplication between processing layers.

## CDC

```text
Silver source events : 1000
Gold source events   : 1000

Result: PASS
```

## openFDA

```text
Silver report IDs : 100
Gold report count : 100

Result: PASS
```

Reconciliation therefore confirms that the validated source-level records remained represented in the Gold outputs.

---

# 11. Duplicate Handling

Duplicate handling occurs at the appropriate dataset grain.

### CDC

```text
event_id
```

is the deterministic event identity.

### openFDA

```text
safetyreportid
```

is the report-level identity.

### Gold

Gold datasets use their defined analytical grain rather than assuming that source IDs remain unique after aggregation.

This distinction is important because uniqueness must always be evaluated relative to the intended grain.

---

# 12. Event Time and Ingestion Time

The CDC streaming pipeline preserves both:

```text
event_time
ingestion_time
```

These fields have different meanings.

```text
event_time
    = source/update time carried by the event

ingestion_time
    = time the platform received the event
```

Because Day 4 replays historical CDC data, the two timestamps can differ by years.

This is intentional and allows the architecture to demonstrate event-time-aware processing.

Late events are detected in the Day 4 consumer using partition-aware event-time comparison.

The current Day 4 implementation logs late-event detection but does not persist a separate late-event status column in Bronze.

---

# 13. Quarantine

Invalid events are not silently dropped.

The Day 4 streaming consumer routes malformed events to:

```text
healthcare/quarantine/cdc/
```

The final validation contained:

```text
1
```

quarantined malformed event.

The recorded reason was:

```text
Missing event fields: event_time
```

Quarantine provides an operational path for investigating and replaying invalid input without contaminating the trusted Bronze layer.

---

# 14. Hard Validation vs Diagnostic Checks

The project distinguishes between hard validation failures and diagnostic observations.

## Hard Validation

A condition that prevents a record or dataset from being accepted.

Examples:

* missing required event identity
* missing required timestamp
* malformed event envelope
* missing required report ID
* duplicate identity where uniqueness is mandatory
* missing expected output

## Diagnostic / Informational Validation

A condition that should be observed and investigated but should not automatically invalidate the dataset without domain justification.

Examples:

* unusual statistical distributions
* historical reporting revisions
* changes in source reporting patterns
* statistical outliers

This distinction avoids embedding unsupported business assumptions into the data pipeline.

---

# 15. CDC Domain Considerations

CDC aggregate data can be retrospectively updated by the source.

Therefore, simple rules such as:

```text
new_cases <= total_cases
```

should not automatically be treated as hard data-quality failures without confirming the source's reporting semantics.

Historical corrections and reporting revisions can affect aggregate relationships.

The pipeline therefore emphasizes:

* structural validity
* typing
* identity
* completeness
* reconciliation

rather than imposing unsupported domain constraints.

---

# 16. Idempotency

The transformation layer is designed for repeatable processing.

CDC uses:

```text
event_id
```

as the deterministic event identity.

openFDA uses:

```text
safetyreportid
```

as the report-level identity.

These identifiers allow duplicate detection during repeated processing.

The intended operational property is:

```text
same Bronze input
        │
        ▼
same transformation
        │
        ▼
same Silver/Gold logical result
```

rather than accumulating duplicate analytical records on every execution.

---

# 17. Storage Format

The project uses different formats at different stages:

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

# 18. Compute and Storage Separation

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

# 19. Databricks Boundary

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

# 20. Validation Script

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

# 21. Final Day 5 Validation Evidence

The complete validation result was:

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

# 22. Test Strategy

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

# 23. Current Limitations

The current portfolio implementation intentionally does not claim production-grade enterprise monitoring.

Current limitations include:

* late-event status is logged by the CDC consumer but is not persisted as a separate Bronze field
* transformation orchestration is not yet fully automated
* validation results are currently command-line evidence rather than a centralized monitoring store
* no enterprise data-quality platform is used
* no production alerting framework is implemented
* CDC is historical data replayed through a streaming architecture rather than a live CDC source

These limitations are documented deliberately rather than hidden.

---

# 24. Future Improvements

A production implementation could add:

* automated transformation scheduling
* centralized data-quality result tables
* pipeline failure alerting
* data-quality dashboards
* schema drift detection
* data contracts
* automated quarantine reprocessing
* historical quality trend monitoring
* Spark-based distributed transformations where scale requires it
* CI/CD execution of transformation and validation tests

---

# 25. Day 5 Quality Outcome

The Day 5 medallion processing layer passed all implemented Silver/Gold validation controls.

Key evidence:

```text
CDC Silver:
1000 rows
0 duplicate event IDs

CDC Gold:
0 duplicate grain
1000 source events reconciled

openFDA Silver:
100 adverse-event reports
247 reaction records
265 drug records
0 duplicate report IDs

openFDA Gold:
0 duplicate grain
100 report IDs reconciled

Overall:
SILVER / GOLD VALIDATION: PASS
```

The lakehouse now has a validated Bronze → Silver → Gold processing path ready for the downstream Synapse, Power BI, and ML stages.
