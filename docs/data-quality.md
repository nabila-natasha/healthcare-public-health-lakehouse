# Data Quality

## Quality objectives

The pipeline applies data-quality controls across the Bronze, Silver, and Gold layers.

The main objectives are to:

* preserve source records without silent loss
* detect malformed and structurally invalid events
* identify duplicate event deliveries
* validate required fields and data types
* preserve event time separately from ingestion time
* reconcile records between transformation layers
* validate analytical grain before Gold consumption
* isolate invalid records in quarantine rather than silently discarding them

Validation is designed to distinguish between:

* **ingestion quality** — whether an event can be safely accepted
* **transformation quality** — whether records can be converted into typed analytical datasets
* **analytical quality** — whether Gold metrics reconcile to their source data

---

## Bronze validation

Bronze is the first durable analytical landing layer after ingestion.

### CDC streaming validation

CDC records are replayed through Azure Event Hubs using a streaming architecture. Each event contains an envelope with:

* `event_id`
* `event_time`
* `ingestion_time`
* `source`
* `source_dataset_id`
* `payload`

The consumer validates the required event envelope before writing a record to Bronze.

Checks include:

* required event fields are present
* `event_time` is present
* `ingestion_time` is generated during ingestion
* payload structure is preserved
* malformed events are routed to quarantine
* duplicate event deliveries are detected using `event_id`

The deterministic `event_id` is generated from the CDC business-record identity:

```text
state | start_date | end_date
```

This allows duplicate delivery to be identified independently of the Event Hubs offset.

### Late-event handling

The streaming consumer also compares event time with previously observed event time within each Event Hubs partition.

Late events are **detected and logged operationally** but are not persisted as a separate Bronze status field.

This distinction is intentional:

* `event_time` represents when the source record was updated
* `ingestion_time` represents when the pipeline received the event
* Event Hubs offsets represent stream position
* a late event can therefore have an older `event_time` while arriving later in the stream

### Day 4 validation evidence

The final Day 4 replay contained:

* 1,002 Event Hubs messages
* 1,002 RAW files
* 1,000 valid Bronze records
* 1 quarantined malformed event

The malformed event was intentionally created without `event_time` and was routed to quarantine.

The final ADLS layout was:

```text
healthcare/
├── raw/
│   └── cdc/day4_final_20260921/
├── bronze/
│   └── cdc/day4_final_20260921/
└── quarantine/
    └── cdc/day4_final_20260921/
```

The difference between RAW and Bronze is explained by duplicate and malformed-event handling rather than silent record loss.

---

## Batch Bronze validation

The openFDA ingestion pipeline uses Azure Data Factory to copy the source API response into ADLS RAW.

The openFDA Bronze processing validates:

* expected source structure
* presence of adverse-event records
* unique `safetyreportid`
* extraction of nested reaction and drug structures
* preservation of source information

The Day 3 controlled ingestion produced 100 source adverse-event records for transformation.

---

## Silver validation

Silver contains typed and normalized datasets suitable for analytical processing.

### CDC Silver

The CDC Bronze-to-Silver transformation:

```text
transformations/silver/cdc_bronze_to_silver.py
```

performs:

* recursive Bronze JSON discovery
* event-envelope flattening
* payload extraction
* timestamp conversion
* date conversion
* numeric type conversion
* required-column validation
* duplicate detection by `event_id`
* Parquet output

The CDC Silver dataset contains 1,000 records across 60 state/geographic reporting entities.

Validation checks include:

* 1,000 expected records
* 60 states
* zero duplicate event IDs
* required fields populated
* expected timestamp/date types
* expected numeric fields available

### openFDA Silver

The openFDA Bronze-to-Silver transformation:

```text
transformations/silver/openfda_bronze_to_silver.py
```

normalizes the nested source structure into three datasets:

```text
adverse_events
adverse_event_reactions
adverse_event_drugs
```

This preserves the one-to-many relationships between an adverse-event report and its associated reactions and drugs.

Validation results for the controlled dataset:

* 100 adverse-event records
* 247 reaction records
* 265 drug records
* zero duplicate report IDs

The Silver outputs are stored as Parquet to provide typed, columnar datasets for downstream analytical processing.

---

## Gold validation

Gold contains business-level analytical datasets at explicitly defined grains.

### CDC Gold

The CDC Silver-to-Gold transformation:

```text
transformations/gold/cdc_silver_to_gold.py
```

aggregates records at:

```text
state + start_date + end_date
```

The Gold dataset contains:

* `state`
* `start_date`
* `end_date`
* `total_cases`
* `new_cases`
* `total_deaths`
* `new_deaths`
* `historic_cases`
* `historic_deaths`
* `source_event_count`
* `cumulative_death_case_ratio_pct`

The derived metric:

```text
cumulative_death_case_ratio_pct =
    total_deaths / total_cases * 100
```

is a portfolio-derived analytical metric. It is **not represented as an official CDC published measure**.

Where `total_cases` is zero, the ratio remains undefined rather than forcing an artificial zero value.

CDC Gold validation checks include:

* 1,000 expected rows
* 60 states
* zero duplicate Gold grain
* required fields populated
* Gold source-event count reconciles to Silver records

### openFDA Gold

The openFDA Silver-to-Gold transformation:

```text
transformations/gold/openfda_silver_to_gold.py
```

aggregates reports at:

```text
reporter_country + transmission_date
```

Gold metrics include:

* adverse-event report count
* serious-report count
* death-report count
* expedited-report count
* corresponding percentages

Validation checks include:

* expected Gold row count
* country coverage
* zero duplicate analytical grain
* required fields populated
* Gold report counts reconcile to Silver report IDs

The 100 Silver adverse-event records producing 15 Gold rows is expected because Gold uses an aggregate business grain rather than one row per source report.

---

## Reconciliation

Cross-layer reconciliation is used to detect unexpected record loss or duplication during transformation.

### CDC

```text
Silver source events: 1,000
Gold source events:   1,000
Result: PASS
```

The sum of `source_event_count` in CDC Gold equals the number of valid CDC Silver records.

### openFDA

```text
Silver report IDs: 100
Gold report count: 100
Result: PASS
```

The total Gold adverse-event report count equals the number of unique Silver report IDs.

These reconciliations provide evidence that aggregation changed the analytical grain without unexpectedly dropping source records.

---

## Quarantine

Records failing structural validation are stored separately rather than silently discarded.

For the Day 4 CDC streaming test, the deliberately malformed event was quarantined because:

```text
Missing event fields: event_time
```

The quarantine path was:

```text
healthcare/quarantine/cdc/day4_final_20260921/
```

Quarantine therefore provides an auditable location for rejected events and supports later investigation without contaminating the Bronze analytical dataset.

---

## Testing strategy

The repository separates **CI-safe tests** from **cloud/data validation**.

### Automated repository tests

The `tests/` directory contains deterministic tests that can run without Azure credentials, external APIs, or an active Azure subscription.

The current Day 5 structural test validates:

* required transformation scripts exist
* the Silver/Gold validation script exists
* expected Medallion transformation directories exist
* Day 5 documentation exists

These tests are suitable for GitHub Actions CI.

### Data validation scripts

The script:

```text
scripts/silver_gold_validations.py
```

validates the actual generated Day 5 Parquet outputs.

It checks:

* expected files exist
* row counts
* state/country coverage
* duplicate keys
* required fields
* Silver-to-Gold reconciliation
* expected parent/child record counts

This validation requires generated transformation outputs and is therefore separate from the CI-safe repository tests.

### External dependency isolation

Automated repository tests should not depend on:

* live Azure resources
* Azure subscription availability
* Event Hubs
* Azure Data Factory
* external APIs
* Power BI
* production credentials

This allows CI to remain useful even when the Azure trial environment is unavailable.

---

## Data-quality principles

The project follows several practical data-engineering principles.

### 1. Do not silently discard records

Invalid records are quarantined or explicitly excluded through documented validation logic.

### 2. Preserve source and processing time separately

Event time and ingestion time answer different operational questions and should not be conflated.

### 3. Detect duplicate delivery

Streaming systems provide at-least-once delivery patterns in which the same event can potentially be delivered more than once. Deterministic event IDs provide a basis for duplicate detection.

### 4. Validate analytical grain

Gold datasets explicitly define their grain before aggregation. This reduces the risk of accidental double counting.

### 5. Reconcile transformations

Source-to-target reconciliation provides evidence that aggregation and transformation did not unexpectedly lose records.

### 6. Separate data validation from application testing

Cloud data validation verifies actual datasets and resources, while CI tests verify repository structure and deterministic code behavior without requiring cloud access.

---

## Current validation status

The current Day 5 validation completed successfully:
```text
CDC Silver: PASS
CDC Gold: PASS
CDC reconciliation: PASS

openFDA Silver: PASS
openFDA Gold: PASS
openFDA reconciliation: PASS

Overall Silver / Gold validation: PASS
```

The repository test suite also completed successfully:

```text
4 passed
```

These checks provide validation evidence for the current controlled datasets while keeping the CI
pipeline independent of live Azure resources.
