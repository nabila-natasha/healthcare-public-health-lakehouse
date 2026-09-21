# Data Sources

This document describes the external data sources used by the healthcare public-health lakehouse and how each source is ingested into the platform.

The project intentionally distinguishes between:

```text
Source characteristics
        vs.
Platform ingestion architecture
```

A source may be a batch or historical dataset while still being processed through a streaming architecture for engineering purposes.

---

# 1. openFDA

## Source

openFDA

## Domain

Healthcare / pharmaceutical safety

## Dataset

FDA adverse event data

## Access pattern

REST/HTTP API

## Ingestion pattern

Batch

## Azure component

Azure Data Factory

## Destination

ADLS Gen2 RAW:

```text
healthcare/raw/openfda/
```

---

## API request

The Day 3 implementation uses the openFDA adverse-event endpoint with a bounded request:

```text
drug/event.json?limit=100
```

The bounded request is intentional.

The objective of Day 3 is to demonstrate the ingestion architecture and downstream data handling rather than retrieve the complete openFDA dataset.

---

## Why batch?

The source is accessed by explicitly requesting a collection of records from a REST API.

The project therefore treats openFDA as a batch ingestion workload rather than an operational event stream.

The ingestion flow is:

```text
openFDA REST API
      ↓
Azure Data Factory
      ↓
ADLS Gen2 RAW
      ↓
Python transformation
      ↓
ADLS Gen2 Bronze
```

---

## Day 3 implementation

The ADF Copy Activity successfully retrieved a response containing:

```text
100 adverse-event records
```

The ADF activity wrote one JSON document to ADLS RAW.

Important distinction:

```text
ADF rows read/copied = 1 JSON document
openFDA records      = 100 adverse-event records
```

The 100 records are contained inside the JSON response's:

```text
results[]
```

array.

---

## RAW output

Actual Day 3 RAW path:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

Actual file size:

```text
1,599,087 bytes
```

---

## Bronze representation

The RAW response was transformed into a Bronze CSV during development.

Bronze grain:

```text
One row per safetyreportid
```

Validation results:

```text
Bronze rows            : 100
Unique safetyreportid  : 100
Duplicate IDs          : 0
Columns                : 17
```

Bronze output:

```text
healthcare/bronze/openfda/openfda_adverse_events.csv
```

The Bronze transformation promotes selected scalar and nested attributes into columns.

Repeated arrays such as:

```text
reaction[]
drug[]
```

are retained as JSON strings.

This avoids creating a reaction × drug row multiplication at the Bronze layer.

Further normalization can be performed later at the Silver layer if downstream analytics require it.

---

## Source quality observations

The source was inspected before finalizing the Bronze representation.

For the 100 retrieved records:

```text
safetyreportid missing       : 0
transmissiondate missing     : 0
receivedate missing          : 0
receiptdate missing          : 0
duplicate safetyreportid     : 0
```

The source also contained missing values for some optional fields.

For example:

```text
seriousnessdeath missing     : 96 / 100
```

Missing values are preserved as NULL rather than being interpreted as a negative value.

---

## Current limitations

The Day 3 implementation is intentionally bounded.

It does not yet provide:

* complete historical extraction
* API pagination
* incremental extraction
* watermarking
* automated RAW-to-Bronze orchestration
* schema-drift automation
* production monitoring

These are documented as future production enhancements rather than being presented as implemented capabilities.

---

## Future enhancements

Future versions may include:

* API pagination
* incremental extraction
* watermarking
* run-specific or date-partitioned RAW paths
* scheduled execution
* retry handling
* failure notifications
* metadata-driven ingestion
* schema-drift detection
* automated RAW-to-Bronze orchestration
* source freshness monitoring

---

# 2. CDC Public-Health Surveillance Data

## Source

Centers for Disease Control and Prevention (CDC)

## Dataset

**Weekly United States COVID-19 Cases and Deaths by State - ARCHIVED**

## CDC Socrata dataset ID

```text
pwn4-m3yp
```

## Source API

```text
https://data.cdc.gov/resource/pwn4-m3yp.json
```

## Domain

Public health / COVID-19 case surveillance

---

## Source characteristics

The CDC dataset contains historical state-level aggregate COVID-19 reporting data.

Important source fields include:

| Field                 | Description                        |
| --------------------- | ---------------------------------- |
| `date_updated`        | Source/update timestamp            |
| `state`               | State or jurisdiction              |
| `start_date`          | Start of reporting period          |
| `end_date`            | End of reporting period            |
| `tot_cases`           | Total reported cases               |
| `new_cases`           | New reported cases                 |
| `tot_deaths`          | Total reported deaths              |
| `new_deaths`          | New reported deaths                |
| `new_historic_cases`  | Newly identified historical cases  |
| `new_historic_deaths` | Newly identified historical deaths |

The source is archived and therefore represents historical public-health reporting rather than a current operational event feed.

---

# 3. Role of CDC Data in This Project

The CDC dataset is used as the real public-health source for the project's streaming simulation.

The project does **not** claim that the CDC dataset itself is a live Kafka, Event Hubs, or operational healthcare event stream.

Instead:

```text
Real historical CDC data
        +
Controlled simulated streaming transport
```

is used to demonstrate event-driven ingestion engineering.

---

# 4. Controlled CDC Fixture

A controlled fixture was created from the CDC source data:

```text
data/fixtures/cdc_sample_1000.json
```

The fixture contains:

```text
1,000 source records
```

Profiling confirmed:

```text
Records                    : 1,000
State/jurisdiction values  : 60
Nulls across selected fields: 0
```

The fixture is used because it makes the streaming test:

* deterministic
* reproducible
* safe to replay
* independent of changes to the external API

This is particularly useful for CI/testing and engineering validation.

---

# 5. CDC Ingestion Pattern

The CDC source is historical.

The project therefore uses:

```text
Historical CDC dataset
        ↓
Controlled replay
        ↓
Azure Event Hubs
        ↓
Streaming consumer
        ↓
ADLS Gen2
```

The Event Hubs layer is a simulated transport for the historical records.

It should therefore be described as:

```text
Historical public-health data
+
Simulated event-streaming transport
```

and not as:

```text
Live CDC healthcare event stream
```

---

# 6. Event-Time Design

The project explicitly separates event time from platform ingestion time.

For the CDC replay:

```text
event_time = date_updated
```

The source/update timestamp is therefore carried into the event envelope as the business/source event time.

The platform ingestion timestamp is generated when the event is processed:

```text
ingestion_time = current UTC timestamp
```

Example:

```text
event_time:
2020-04-23

ingestion_time:
2026-09-21
```

This distinction demonstrates an important streaming concept:

```text
event_time
=
when the source event represents

ingestion_time
=
when the platform receives/processes it
```

A historical record can therefore have an old event time while being ingested into the platform years later.

---

# 7. CDC Event Envelope

Each replayed CDC record is wrapped in an event envelope containing:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

The original CDC record is preserved inside:

```text
payload
```

This separates source data from platform/event metadata while retaining the original source information.

---

# 8. Event Identity

A deterministic event ID is generated using:

```text
state|start_date|end_date
```

The concatenated value is hashed using SHA-256.

Conceptually:

```text
event_id =
SHA256(
    state
    + "|"
    + start_date
    + "|"
    + end_date
)
```

The purpose is to provide a stable logical identifier for the same source event.

This enables duplicate deliveries to be identified using the same:

```text
event_id
```

The event ID therefore acts as the idempotency key for the controlled replay.

---

# 9. Streaming Transport

The CDC replay uses:

```text
Azure Event Hubs
```

Event Hub:

```text
healthcare-events
```

Configuration:

```text
Partitions : 4
Retention  : 7 days
```

Event Hubs provides partition and offset metadata for received messages.

These values are used for:

* tracing
* debugging
* operational investigation
* replay analysis
* audit evidence

An offset is position-specific to a partition.

For example:

```text
partition 0, offset 1206
```

means the message is at offset `1206` within partition `0`.

It does not mean that 1,206 total messages were sent to the entire Event Hub before that message.

---

# 10. Day 4 Replay

The Day 4 replay uses:

```text
1,000 logical CDC source events
```

The controlled test intentionally introduces additional delivery scenarios.

The final replay contains:

```text
999 normal valid records
+ 1 deliberately delayed valid record
+ 1 duplicate delivery
+ 1 malformed event
--------------------------------
1,002 Event Hub messages
```

The delayed record remains logically valid.

Its purpose is to exercise late-event detection by changing its event-time ordering.

The duplicate delivery tests idempotency.

The malformed event tests quarantine handling.

---

# 11. ADLS Landing

The Day 4 streaming pipeline uses three ADLS logical layers:

```text
RAW
Bronze
Quarantine
```

### RAW

```text
healthcare/raw/cdc/
```

RAW preserves every received Event Hub message.

Final validation prefix:

```text
raw/cdc/day4_final_20260921
```

Final count:

```text
1,002 files
```

---

### Bronze

```text
healthcare/bronze/cdc/
```

Bronze contains valid events after consumer validation and duplicate handling.

Final validation prefix:

```text
bronze/cdc/day4_final_20260921
```

Final count:

```text
1,000 files
```

---

### Quarantine

```text
healthcare/quarantine/cdc/
```

Invalid events are retained separately together with diagnostic information.

Final validation prefix:

```text
quarantine/cdc/day4_final_20260921
```

Final count:

```text
1 file
```

---

# 12. Day 4 Final Reconciliation

The independently validated final state is:

| Layer              | Count |
| ------------------ | ----: |
| Event Hub messages | 1,002 |
| RAW                | 1,002 |
| Bronze             | 1,000 |
| Quarantine         |     1 |

The logical reconciliation is:

```text
1,002 Event Hub messages
        |
        +-- 1,000 valid logical source events
        |
        +-- 1 duplicate delivery
        |
        +-- 1 malformed event
```

The duplicate does not create an additional Bronze record.

The malformed event is retained in Quarantine.

RAW retains all received messages.

---

# 13. Data-Quality Controls

Day 4 demonstrates:

### Required-field validation

Required event metadata includes:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

Missing required fields result in quarantine.

### Duplicate detection

Duplicate deliveries are identified using:

```text
event_id
```

### Late-event detection

The consumer compares event time against the latest event time observed within the same Event Hubs partition.

The delayed event was intentionally included to exercise this logic.

The current implementation detects and logs the late event but does not persist a dedicated `late_event` flag in Bronze.

### RAW preservation

Every received Event Hub message is retained in RAW.

### Quarantine

Invalid events are retained with diagnostic metadata and the validation failure reason.

### Reconciliation

ADLS layer counts are independently validated against the expected replay composition.

---

# 14. Consumer Processing Model

The logical processing flow is:

```text
Event Hub message
       ↓
Read event
       ↓
Validate required fields
       ↓
   +---+---+
   |       |
invalid   valid
   |       |
   v       v
Quarantine  Check duplicate
               |
          +----+----+
          |         |
      duplicate     new
          |         |
          v         v
        Ignore   Check late event
                     |
                     v
                   Bronze
```

The consumer preserves:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

and operational metadata such as Event Hubs partition and offset where applicable.

---

# 15. Consumer Group

The final Day 4 validation used a dedicated consumer group:

```text
healthcare-bronze-consumer-day4-final-20260921
```

The consumer used:

```text
EVENT_HUB_AUTO_OFFSET_RESET=latest
```

The dedicated consumer group isolates the Day 4 validation run from other consumers and prevents the test from unintentionally sharing consumption state with an earlier consumer.

---

# 16. Synapse Integration

A Synapse linked service was configured against:

```text
stlakehousebello
```

The linked service:

```text
ls_adls_healthcare
```

successfully located the project ADLS path.

However, the current Serverless SQL `OPENROWSET` approach did not successfully return the Bronze JSON objects as usable query rows.

The issue was isolated to the SQL/JSON parsing layer rather than the ADLS landing itself.

Therefore:

```text
ADLS validation
=
authoritative Day 4 count validation
```

The project does **not** claim successful Synapse SQL querying of the Day 4 Bronze JSON data.

---

# 17. Security and Configuration

Azure credentials and connection strings are kept outside source-controlled application code.

Relevant environment variables include:

```text
EVENT_HUB_CONNECTION_STRING
AZURE_STORAGE_CONNECTION_STRING
```

Secrets must not be committed to GitHub.

The local configuration may be loaded from:

```text
.env
```

using:

```bash
set -a
source .env
set +a
```

---

# 18. Production Evolution

The Day 4 implementation demonstrates production-oriented design principles at portfolio scale.

A production implementation would additionally consider:

* durable checkpoint/state management
* persistent idempotency state
* managed streaming compute
* schema registry or formal schema management
* automated monitoring
* dead-letter/quarantine monitoring
* alerting
* replay controls
* source freshness monitoring
* automated deployment
* managed secret storage
* partition strategy based on workload characteristics

The current project deliberately does not claim these capabilities as implemented production services.

---

# 19. Source and Architecture Summary

| Source               | Source type                      | Project ingestion          | Transport  | Destination                    |
| -------------------- | -------------------------------- | -------------------------- | ---------- | ------------------------------ |
| openFDA              | REST API                         | Batch                      | ADF        | ADLS RAW → Bronze              |
| CDC archived dataset | Historical public-health dataset | Simulated streaming replay | Event Hubs | ADLS RAW → Bronze / Quarantine |

The key architectural distinction is:

```text
openFDA
    = batch source
    = batch ingestion

CDC historical data
    = historical source
    = simulated streaming ingestion
```

Neither source is represented as a live operational healthcare event feed.

---

# 20. Day 4 Outcome

Day 4 successfully demonstrates a controlled historical public-health replay through an Azure event-streaming architecture.

The final validation produced:

```text
RAW        = 1,002
Bronze     = 1,000
Quarantine = 1
```

The pipeline demonstrates:

```text
ingest
  ↓
preserve
  ↓
validate
  ↓
deduplicate
  ↓
detect late events
  ↓
quarantine invalid data
  ↓
reconcile
```

The architecture therefore demonstrates event-streaming engineering while remaining explicit that:

```text
CDC source = real historical public-health data

Event Hubs transport = simulated streaming transport
```

This distinction is maintained throughout the project documentation.
