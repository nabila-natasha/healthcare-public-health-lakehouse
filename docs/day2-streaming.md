# Day 2 — Streaming CDC Ingestion and Lake Validation

## 1. Objective

Day 2 implements and validates a small streaming-style CDC ingestion pipeline for the Healthcare Public Health Lakehouse.

The objective is to demonstrate:

* Event-driven ingestion using Azure Event Hubs
* Kafka-compatible Python producer and consumer patterns
* Raw event preservation in Azure Data Lake Storage Gen2 (ADLS Gen2)
* Validation and duplicate detection
* Bronze-layer creation
* Quarantine handling for invalid events
* Serverless SQL validation using Azure Synapse
* Clear separation between raw received data and processed analytical data

The pipeline uses a deterministic synthetic healthcare CDC fixture so that the ingestion behaviour can be reproduced and validated consistently.

---

## 2. Architecture

```text
Synthetic CDC Fixture
        |
        v
Python Replay Producer
        |
        v
Azure Event Hubs
        |
        v
Kafka-compatible Python Consumer
        |
        v
ADLS Gen2 RAW
        |
        v
Validation + Duplicate Detection
        |
        +----------------------+
        |                      |
        v                      v
     BRONZE                QUARANTINE
        |
        v
Synapse Serverless SQL
        |
        v
Validation / Analytics
```

The logical data flow is:

```text
Event Hubs
    |
    v
Consumer
    |
    v
RAW
    |
    +---- invalid event ------> QUARANTINE
    |
    +---- valid event
              |
              +---- duplicate ------> skipped
              |
              +---- unique ---------> BRONZE
```

This design deliberately preserves all successfully received messages in RAW before applying validation and deduplication.

---

## 3. CDC Fixture

A deterministic synthetic CDC dataset was created at:

```text
data/fixtures/healthcare_cdc.csv
```

The fixture contains 10 source events.

Example structure:

```text
event_id,event_time,patient_id,event_type,region,status
cdc-0001,2026-09-19T08:00:00Z,P001,admission,MY,active
cdc-0002,2026-09-19T08:00:05Z,P002,discharge,MY,closed
...
```

The fixture represents simplified healthcare operational events such as:

* admission
* discharge
* transfer

The dataset intentionally contains valid records so that the Day 2 pipeline can focus on ingestion, preservation, duplicate detection, and validation.

---

## 4. Event Hubs Ingestion

Azure Event Hubs was used as the streaming ingestion layer.

Resources:

```text
Event Hubs Namespace:
eh-lakehouse-bello

Event Hub:
healthcare-events

Partitions:
4
```

The Python producer is located at:

```text
ingestion/replay/producer.py
```

The producer reads the deterministic CDC fixture and publishes each event to Event Hubs using the Kafka-compatible endpoint.

Each event contains:

* `event_id`
* `event_time`
* `ingestion_time`
* `source`
* `patient_id`
* `event_type`
* `region`
* `status`

The producer intentionally replays event `cdc-0005` once to simulate a duplicate delivery.

Therefore:

```text
Source fixture events: 10
Messages sent to Event Hubs: 11
```

The duplicate was intentionally introduced to demonstrate why downstream idempotency and deduplication are required in event-driven pipelines.

---

## 5. RAW Layer

The Event Hubs consumer is located at:

```text
ingestion/event_hubs/consumer.py
```

The consumer reads events from Event Hubs and writes the received messages to ADLS Gen2.

Storage account:

```text
stlakehousebello
```

Filesystem:

```text
healthcare
```

RAW path:

```text
raw/cdc/
```

The RAW data is partitioned by ingestion date, Event Hubs partition, and offset.

Example:

```text
raw/
└── cdc/
    └── ingestion_date=2026-09-19/
        └── partition=2/
            └── offset=0.json
```

Each RAW record preserves both the original event and ingestion metadata.

Example structure:

```json
{
  "event": {
    "event_id": "cdc-0001",
    "event_time": "2026-09-19T08:00:00Z",
    "ingestion_time": "2026-09-19T08:27:44.758624+00:00",
    "source": "cdc_replay",
    "patient_id": "P001",
    "event_type": "admission",
    "region": "MY",
    "status": "active"
  },
  "event_hub_partition": 2,
  "event_hub_offset": 0,
  "received_at": "2026-09-19T09:40:21.222675+00:00"
}
```

RAW intentionally contains duplicate messages.

This provides an audit-friendly record of what the consumer actually received before downstream processing.

---

## 6. Validation and Deduplication

The consumer performs basic validation before accepting events into Bronze.

Required fields are:

```text
event_id
event_time
ingestion_time
source
patient_id
event_type
region
status
```

The validation process checks that:

1. Required fields are present.
2. `event_id` is not empty.
3. `event_time` is not empty.

After validation, duplicate `event_id` values are detected.

For the Day 2 test:

```text
cdc-0005
```

was intentionally delivered twice.

The first occurrence was accepted.

The second occurrence was detected as a duplicate and skipped from Bronze.

This demonstrates an important streaming data engineering principle:

> A message being delivered successfully does not guarantee that it is delivered exactly once.

Downstream systems therefore need idempotency or deduplication logic.

---

## 7. Bronze Layer

Valid and unique events are written to:

```text
bronze/cdc/
```

The Bronze layer contains processed events that have passed basic validation and duplicate detection.

Example:

```text
bronze/
└── cdc/
    └── ingestion_date=2026-09-19/
        ├── cdc-0001.json
        ├── cdc-0002.json
        ├── cdc-0003.json
        └── ...
```

Bronze records also contain:

```text
processed_time
```

This timestamp records when the event was accepted into the Bronze processing layer.

For the Day 2 test:

```text
RAW records: 11
Unique event IDs: 10
Bronze records: 10
```

Therefore, the duplicate was preserved in RAW but not propagated into Bronze.

---

## 8. Quarantine Layer

Invalid records are designed to be written to:

```text
quarantine/cdc/
```

The quarantine layer provides a location for events that cannot safely enter Bronze.

Examples of potential quarantine reasons include:

* Invalid JSON
* Missing required fields
* Empty `event_id`
* Empty `event_time`

The quarantine record contains diagnostic information such as:

```text
reason
partition
offset
received_at
```

The Day 2 test batch contained only valid events.

Therefore:

```text
Quarantined records: 0
```

The quarantine mechanism is nevertheless implemented so that the pipeline has an explicit failure-handling path rather than silently discarding invalid messages.

---

## 9. Synapse Serverless Validation

Azure Synapse Serverless SQL was used to validate the ADLS data without loading the files into a dedicated relational database.

A database master key was created to protect the database-scoped credential.

The Synapse database uses:

```text
HealthcareWorkspaceIdentity
```

as a database-scoped credential with:

```sql
IDENTITY = 'Managed Identity'
```

An external data source was then created:

```text
HealthcareLake
```

which points to the ADLS Gen2 healthcare filesystem.

The external data source uses:

```text
https://stlakehousebello.dfs.core.windows.net/healthcare
```

Synapse Serverless can then query JSON files using `OPENROWSET`.

The JSON content is read as text and individual fields are extracted using:

```sql
JSON_VALUE()
```

This allows standard SQL operations such as:

```sql
SELECT
COUNT(*),
GROUP BY,
HAVING,
ORDER BY
```

to be applied to the lake data.

The validation queries are stored in:

```text
sql/day2_validation.sql
```

---

## 10. Validation Results

The Day 2 pipeline produced the following expected results:

| Validation                 | Expected Result | Actual Result |
| -------------------------- | --------------: | ------------: |
| Source fixture events      |              10 |            10 |
| Event Hubs messages sent   |              11 |            11 |
| RAW records                |              11 |            11 |
| Unique event IDs in RAW    |              10 |            10 |
| Duplicate event            |      `cdc-0005` |    `cdc-0005` |
| Occurrences of duplicate   |               2 |             2 |
| Bronze records             |              10 |            10 |
| Duplicate Bronze event IDs |               0 |             0 |
| Quarantined records        |               0 |             0 |

The results demonstrate that:

```text
10 source events
       |
       v
11 Event Hubs messages
       |
       v
11 RAW records
       |
       v
10 unique valid events
       |
       v
10 Bronze records
```

The duplicate was therefore successfully retained in RAW for auditability while being prevented from entering Bronze.

---

## 11. Key Design Decisions

### 11.1 RAW before deduplication

RAW stores all successfully received messages before duplicate removal.

This provides:

* auditability
* replay capability
* troubleshooting evidence
* visibility into source delivery behaviour

If a downstream transformation produces an unexpected result, engineers can inspect what was actually received.

---

### 11.2 Bronze after validation

Bronze contains events that have passed basic validation and duplicate detection.

This provides a cleaner contract for downstream transformation.

The separation is:

```text
RAW = what was received

BRONZE = what was accepted for processing
```

---

### 11.3 Duplicate detection by event ID

`event_id` is treated as the logical business/event identifier.

Duplicate messages with the same `event_id` are not propagated to Bronze.

This is a simplified demonstration of idempotent processing.

---

### 11.4 Event Hubs partition metadata

RAW preserves:

```text
event_hub_partition
event_hub_offset
```

These values provide useful operational metadata for troubleshooting and replay analysis.

Because Event Hubs is partitioned, global ordering across all events should not be assumed.

---

### 11.5 Timestamps

Several timestamps are intentionally retained:

```text
event_time
ingestion_time
received_at
processed_time
```

They represent different stages of the data lifecycle.

```text
event_time
    |
    v
ingestion_time
    |
    v
received_at
    |
    v
processed_time
```

This allows future analysis of ingestion and processing latency.

---

## 12. Security

No credentials or connection strings are committed to GitHub.

Configuration is supplied through environment variables.

The repository contains:

```text
.env.example
```

but does not contain the real `.env` file.

The `.gitignore` configuration prevents local environment files and secrets from being committed.

Synapse uses a managed identity for access to the ADLS external data source.

For production, the preferred pattern would be:

```text
Managed Identity
        +
Azure RBAC
        +
Least-privilege access
```

rather than embedding storage credentials in application code.

The Python Day 2 implementation currently uses an environment-provided Event Hubs connection string and storage connection string as a practical development approach.

This is documented as a development simplification rather than a production security pattern.

---

## 13. Limitations

This Day 2 implementation is intentionally small and educational.

The current consumer maintains processed event IDs in an in-memory Python set:

```text
processed_event_ids
```

This means the deduplication state is lost if the consumer process restarts.

A production implementation would use a durable state mechanism, such as:

* Delta Lake state
* a database
* a checkpoint/state store
* a streaming framework with checkpointing

The current consumer is also a single-process demonstration.

A production architecture would need to consider:

* multiple consumers
* partition scaling
* checkpoint management
* retry policies
* dead-letter handling
* monitoring and alerting
* schema evolution
* durable idempotency
* managed identity authentication
* structured logging

The current Bronze files are JSON.

For larger analytical workloads, a production lakehouse would normally convert validated data into an optimized columnar format such as Parquet or Delta.

---

## 14. Day 2 Outcome

Day 2 successfully demonstrates an end-to-end event ingestion pattern:

```text
Synthetic CDC
     |
     v
Event Hubs
     |
     v
Python Consumer
     |
     v
ADLS RAW
     |
     +---- invalid --> Quarantine
     |
     +---- duplicate --> Skip
     |
     v
ADLS Bronze
     |
     v
Synapse Serverless SQL
```

The implementation demonstrates the following data engineering capabilities:

* Event-driven ingestion
* Kafka-compatible Event Hubs integration
* ADLS Gen2 data lake storage
* Raw/bronze layer separation
* Data validation
* Duplicate detection
* Quarantine handling
* Event metadata preservation
* Serverless SQL querying
* Managed identity integration
* Reproducible test data
* Basic pipeline auditability

The validated Day 2 result is:

```text
10 source events
11 messages delivered
11 RAW records
10 unique events
10 Bronze records
0 duplicate Bronze records
0 quarantined records
```

This establishes the streaming ingestion foundation for the subsequent lakehouse transformation and analytics stages.

