# Day 4 — Historical CDC Replay and Event-Streaming Ingestion

## 1. Overview

Day 4 implements an event-driven ingestion architecture for a historical public-health CDC dataset.

The project takes historical CDC records, wraps them in event envelopes, replays them through Azure Event Hubs, and processes the events into Azure Data Lake Storage Gen2 (ADLS Gen2).

The ingestion flow demonstrates:

* Historical CDC data replayed through a streaming architecture
* Event-time and ingestion-time separation
* Deterministic event IDs
* Azure Event Hubs partitioning
* RAW event landing
* Bronze valid-event landing
* Duplicate detection
* Idempotent processing
* Partition-aware late-event detection
* Malformed-event quarantine
* ADLS-based validation and reconciliation

The CDC source is historical. This project does **not** claim to consume a live CDC event feed.

---

## 2. Business and Engineering Objective

### Business objective

Demonstrate how a public-health data platform can ingest historical health events through an event-streaming architecture while preserving the information needed for:

* operational monitoring
* data-quality controls
* replayability
* auditability
* downstream analytics

### Engineering objective

Build a controlled streaming pipeline that can distinguish between:

1. valid events
2. duplicate deliveries
3. malformed events
4. late-arriving events

The target architecture is:

```text
CDC Historical Dataset
        |
        v
Controlled Replay Producer
        |
        v
Azure Event Hubs
        |
        v
Streaming Consumer
        |
        +--------------------+
        |                    |
        v                    v
      RAW                Validation
        |                    |
        |          +---------+---------+
        |          |                   |
        |          v                   v
        |       Bronze             Quarantine
        |          |
        +----------+
                   |
                   v
              ADLS Gen2
                   |
                   v
          Downstream Analytics
```

---

## 3. Source Dataset

The source dataset is the archived CDC dataset:

**Weekly United States COVID-19 Cases and Deaths by State - ARCHIVED**

CDC Socrata dataset ID:

```text
pwn4-m3yp
```

Source API:

```text
https://data.cdc.gov/resource/pwn4-m3yp.json
```

The dataset contains state-level aggregate COVID-19 reporting data.

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

The CDC metadata indicates that aggregate reporting was discontinued in May 2023, with the final update occurring in June 2023.

Therefore, the dataset is treated as a **historical source** for this portfolio project.

---

## 4. Controlled Test Fixture

A controlled fixture was created from the CDC source data:

```text
data/fixtures/cdc_sample_1000.json
```

The fixture contains:

```text
1,000 source records
```

The dataset profiling confirmed:

* 1,000 records
* 60 state/jurisdiction values
* no nulls across the ten selected source fields
* historical reporting dates beginning in 2020

Using a controlled fixture makes the streaming test:

* deterministic
* reproducible
* safe to replay
* independent of changes to the public API

This is important for engineering validation because the source API may change or retrospectively update historical records.

---

## 5. Event-Time Design

The pipeline explicitly separates **event time** from **ingestion time**.

### Event time

For this project:

```text
event_time = date_updated
```

`date_updated` represents the source/update timestamp associated with the CDC record.

### Ingestion time

The consumer/producer records the actual UTC processing timestamp:

```text
ingestion_time = current UTC timestamp
```

This distinction is important because an event can represent an old historical record while being ingested into the platform much later.

For example:

```text
event_time:
2020-04-23

ingestion_time:
2026-09-21
```

This demonstrates the difference between:

* when the source event belongs to
* when the platform receives/processes it

---

## 6. Event Envelope

Each valid replayed record is wrapped in an event envelope.

The structure is:

```text
event_id
event_time
ingestion_time
source
source_dataset_id
payload
```

Example:

```json
{
  "event_id": "003cf978ff7aa18d7e9410b8df890638cbe4a9ac9af6f0de5a241ed3492971b6",
  "event_time": "2020-04-23T00:00:00.000",
  "ingestion_time": "2026-09-21T05:42:36.901364+00:00",
  "source": "cdc_historical_replay",
  "source_dataset_id": "pwn4-m3yp",
  "payload": {
    "date_updated": "2020-04-23T00:00:00.000",
    "state": "DC",
    "start_date": "2020-04-16T00:00:00.000",
    "end_date": "2020-04-22T00:00:00.000",
    "tot_cases": "3206.0",
    "new_cases": "1009.0",
    "tot_deaths": "127.0",
    "new_deaths": "55.0",
    "new_historic_cases": "0",
    "new_historic_deaths": "0"
  }
}
```

The original CDC record is preserved inside `payload`.

This allows the streaming infrastructure metadata to remain separate from the source data.

---

## 7. Deterministic Event ID

A deterministic event ID is generated using:

```text
state|start_date|end_date
```

The concatenated value is hashed using SHA-256.

Conceptually:

```text
event_id = SHA256(
    state
    + "|"
    + start_date
    + "|"
    + end_date
)
```

The purpose is to provide a stable identifier for the same logical source event.

This enables the consumer to detect duplicate delivery.

For example, if the same CDC event is delivered twice, the two messages have the same:

```text
event_id
```

The consumer can therefore identify the second delivery as a duplicate rather than writing it as another Bronze record.

---

## 8. Azure Architecture

The Day 4 architecture uses:

```text
CDC Historical Dataset
        |
        v
Python Replay Producer
        |
        v
Azure Event Hubs
        |
        v
Python Streaming Consumer
        |
        +-------------------+
        |                   |
        v                   v
      RAW             Event Validation
        |                   |
        |             +-----+------+
        |             |            |
        |             v            v
        |          Bronze      Quarantine
        |             |
        +-------------+
                      |
                      v
                 ADLS Gen2
```

Azure resources used include:

| Component            | Resource                 |
| -------------------- | ------------------------ |
| Resource Group       | `rg-lakehouse-portfolio` |
| Event Hubs Namespace | `eh-lakehouse-bello`     |
| Event Hub            | `healthcare-events`      |
| Event Hub Partitions | 4                        |
| Event Retention      | 7 days                   |
| Storage Account      | `stlakehousebello`       |
| ADLS Filesystem      | `healthcare`             |

---

## 9. Event Hubs

Azure Event Hubs is used as the event-ingestion layer.

The Event Hub is:

```text
healthcare-events
```

It has:

```text
4 partitions
```

and:

```text
7-day message retention
```

Partitions allow Event Hubs to distribute events across multiple logical streams.

Each event has an Event Hubs:

```text
partition
offset
```

The partition identifies the event stream within the Event Hub.

The offset identifies the event's position within that partition.

These values are useful for:

* replay
* debugging
* operational investigation
* tracing
* audit evidence

---

## 10. Historical Replay Scenario

The producer intentionally creates a controlled streaming test rather than simply sending every source record once.

The final replay contains:

```text
999 normal valid records
1 deliberately delayed valid record
1 duplicate delivery
1 malformed event
```

Therefore:

```text
1,002 Event Hub messages
```

are produced.

The logical reconciliation is:

```text
1,000 valid source events
+ 1 duplicate delivery
+ 1 malformed event
--------------------------------
1,002 Event Hub messages
```

The deliberately delayed record is a valid source event whose event-time ordering is intentionally changed to exercise late-event detection.

This is a controlled simulation of a condition that can occur in real streaming systems.

---

## 11. Consumer Processing

The consumer reads events from Azure Event Hubs and performs validation before writing the event to ADLS.

The logical processing flow is:

```text
Event Hub message
       |
       v
Read event
       |
       v
Validate required fields
       |
       +--------------------+
       |                    |
       | invalid            | valid
       v                    v
  Quarantine          Check duplicate
                            |
                   +--------+--------+
                   |                 |
                duplicate          new
                   |                 |
                   v                 v
                Ignore        Check late event
                                     |
                                     v
                                  Bronze
```

The consumer preserves:

* event ID
* event time
* ingestion time
* source
* source dataset ID
* original payload

---

## 12. RAW Layer

The RAW layer preserves every received Event Hub message.

Final validation prefix:

```text
raw/cdc/day4_final_20260921
```

The RAW layer contains:

```text
1,002 files
```

This corresponds to the:

```text
1,002 Event Hub messages
```

The RAW layer therefore provides an audit/replay-oriented landing layer.

Importantly, RAW is not the same as Bronze.

RAW preserves the received events, including events that later fail validation.

This allows downstream processing logic to be changed or investigated without losing the original received message.

---

## 13. Event Hubs Partition and Offset

Event Hubs assigns each received message a partition and offset.

The consumer records these values when processing messages.

For example, a quarantine record contains:

```text
partition: 2
offset: 1999
```

The offset is a position within a specific partition.

It should therefore not be interpreted as a global row number across the entire Event Hub.

For example:

```text
partition 0, offset 1206
```

means the message is at offset 1206 within partition 0.

It does **not** mean that exactly 1,206 total messages were sent to the entire Event Hub before that event.

Different partitions maintain their own offset sequences.

---

## 14. Bronze Layer

The Bronze layer contains valid events after consumer validation.

Final validation prefix:

```text
bronze/cdc/day4_final_20260921
```

The final Bronze count is:

```text
1,000 files
```

This represents the 1,000 logical valid source events.

The Bronze layer preserves the event envelope and source payload while adding processing metadata.

Example Bronze structure:

```json
{
  "event_id": "003cf978ff7aa18d7e9410b8df890638cbe4a9ac9af6f0de5a241ed3492971b6",
  "event_time": "2020-04-23T00:00:00.000",
  "ingestion_time": "2026-09-21T05:42:36.901364+00:00",
  "source": "cdc_historical_replay",
  "source_dataset_id": "pwn4-m3yp",
  "payload": {
    "date_updated": "2020-04-23T00:00:00.000",
    "state": "DC",
    "start_date": "2020-04-16T00:00:00.000",
    "end_date": "2020-04-22T00:00:00.000",
    "tot_cases": "3206.0",
    "new_cases": "1009.0",
    "tot_deaths": "127.0",
    "new_deaths": "55.0",
    "new_historic_cases": "0",
    "new_historic_deaths": "0"
  },
  "processed_time": "2026-09-21T05:47:17.505367+00:00"
}
```

---

## 15. Duplicate Detection and Idempotency

The consumer maintains a set of processed event IDs.

Conceptually:

```text
processed_event_ids
```

Before writing a valid event to Bronze, the consumer checks whether the event ID has already been processed.

The logic is:

```text
if event_id already processed:
    classify as duplicate
    do not write another Bronze record

else:
    process event
    add event_id to processed_event_ids
    write Bronze record
```

This demonstrates an important streaming-engineering principle:

> Message delivery and logical event uniqueness are different concepts.

A message can be delivered more than once.

The pipeline therefore uses the deterministic event ID as an idempotency key.

---

## 16. Late-Event Detection

The consumer implements partition-aware late-event detection.

Late detection compares the current event's `event_time` against the latest event time previously observed within the same Event Hubs partition.

Conceptually:

```text
latest_event_time_by_partition
```

is maintained by the consumer.

For each event:

```text
current event_time
        |
        v
compare with latest event_time
        |
        +----------------------+
        |                      |
   event_time >= latest    event_time < latest
        |                      |
        v                      v
     on-time                  late
```

The intentionally delayed valid record is included in the replay specifically to exercise this logic.

The consumer logs the late-event condition.

The current implementation does **not** persist a separate `late_event` flag into Bronze.

Therefore, the Day 4 implementation demonstrates:

```text
late-event detection and logging
```

rather than a persisted late-event attribute.

---

## 17. Malformed Event Handling

The final replay includes one deliberately malformed event.

The malformed event is missing:

```text
event_time
```

The consumer identifies the missing required field and does not write the event to Bronze.

Instead, it writes the event to the Quarantine layer.

Final validation prefix:

```text
quarantine/cdc/day4_final_20260921
```

Final quarantine count:

```text
1 file
```

The quarantine record preserves:

* original event information
* source
* source dataset ID
* payload
* received timestamp
* Event Hubs partition
* Event Hubs offset
* validation failure reason

This provides traceability for invalid records.

---

## 18. Final ADLS Validation

Independent validation was performed directly against ADLS Gen2.

Final results:

```text
======================================================================
DAY 4 FINAL ADLS VALIDATION
======================================================================
raw/cdc/day4_final_20260921: 1002 files
bronze/cdc/day4_final_20260921: 1000 files
quarantine/cdc/day4_final_20260921: 1 files
======================================================================
```

The final counts are therefore:

| Layer              | Count |
| ------------------ | ----: |
| Event Hub messages | 1,002 |
| RAW                | 1,002 |
| Bronze             | 1,000 |
| Quarantine         |     1 |

---

## 19. Reconciliation

The final counts reconcile as follows:

```text
1,002 Event Hub messages
        |
        +-- 1,000 valid logical source events
        |
        +-- 1 duplicate delivery
        |
        +-- 1 malformed event
```

The expected Bronze result is:

```text
1,000 valid logical events
```

The expected Quarantine result is:

```text
1 malformed event
```

The expected RAW result is:

```text
1,002 received messages
```

Therefore:

```text
RAW = 1,002
Bronze = 1,000
Quarantine = 1
```

The duplicate does not create an additional Bronze record because it is rejected by the idempotency check.

---

## 20. Example Quarantine Record

The final quarantine record was:

```text
quarantine/cdc/day4_final_20260921/ingestion_date=2026-09-21/d87e17c71c97408bfc7099888299b829a6c40e475f5d823c72cc81a16b1a3109-malformed_2_1999.json
```

The record contains:

```json
{
  "event": {
    "event_id": "...-malformed",
    "ingestion_time": "...",
    "source": "cdc_historical_replay",
    "source_dataset_id": "pwn4-m3yp",
    "payload": {
      "date_updated": "2020-04-23T00:00:00.000",
      "state": "DC",
      "start_date": "2020-04-16T00:00:00.000",
      "end_date": "2020-04-22T00:00:00.000",
      "tot_cases": "3206.0",
      "new_cases": "1009.0",
      "tot_deaths": "127.0",
      "new_deaths": "55.0",
      "new_historic_cases": "0",
      "new_historic_deaths": "0"
    }
  },
  "received_at": "...",
  "partition": 2,
  "offset": 1999,
  "reason": "Missing event fields: event_time"
}
```

This demonstrates that a malformed event can be rejected without losing the information required for investigation.

---

## 21. Consumer Group and Offset Strategy

The final validation run used a dedicated Event Hubs consumer group:

```text
healthcare-bronze-consumer-day4-final-20260921
```

The consumer was configured with:

```text
EVENT_HUB_AUTO_OFFSET_RESET=latest
```

Using a dedicated consumer group isolates the Day 4 validation run from other consumers and avoids unintentionally reprocessing messages from an existing consumer group.

The architecture also demonstrates why consumer groups and offsets matter in event-driven systems:

* consumer groups provide independent consumption state
* partitions provide parallel event streams
* offsets provide positions within partitions
* replay can be controlled independently from the producer

---

## 22. Synapse Integration

A Synapse linked service was configured against the project ADLS storage account:

```text
stlakehousebello
```

The linked service is:

```text
ls_adls_healthcare
```

Synapse SQL was able to resolve and locate the Bronze JSON file path in the project ADLS account.

However, the current serverless SQL `OPENROWSET` approach did not successfully return the JSON objects as query rows.

The issue was isolated to the SQL/JSON parsing layer rather than the ADLS landing itself.

The independent ADLS validation therefore remains the authoritative Day 4 count validation.

Day 4 does **not** claim successful Synapse SQL querying of the Bronze JSON data.

This distinction is intentional because the project documentation should reflect what was actually validated rather than claiming an integration succeeded when the final query result was not usable.

---

## 23. Data Quality Controls

The Day 4 pipeline demonstrates several data-quality controls.

### Required-field validation

Events must contain required event metadata such as:

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

Duplicate events are identified using the deterministic:

```text
event_id
```

### Late-event detection

Event-time ordering is evaluated within each Event Hubs partition.

### RAW preservation

Every received message is retained in RAW before downstream validation.

### Quarantine

Invalid events are moved to a dedicated quarantine path with diagnostic metadata.

### Reconciliation

Final layer counts are independently checked against the expected message composition.

---

## 24. Operational Design Principles

The Day 4 implementation demonstrates several production-oriented principles.

### 24.1 Preserve the raw event

The RAW layer provides an immutable-style landing point for received messages.

This supports:

* replay
* debugging
* audit
* downstream reprocessing

### 24.2 Separate event time from processing time

Historical events can arrive long after the time represented by the source record.

Keeping both timestamps prevents the platform from confusing historical business time with platform processing time.

### 24.3 Make processing idempotent

The deterministic event ID provides a stable key for duplicate detection.

### 24.4 Quarantine instead of silently dropping

Invalid events are retained with their failure reason.

### 24.5 Record operational metadata

Partition and offset information provides a way to trace events back to their position in Event Hubs.

### 24.6 Validate independently

The final ADLS counts were validated independently from the streaming consumer's own internal counters.

This reduces the risk of relying entirely on application logs for pipeline validation.

---

## 25. Failure Scenarios Demonstrated

The controlled replay intentionally tests multiple failure conditions.

| Scenario             | Expected behavior                     | Result                    |
| -------------------- | ------------------------------------- | ------------------------- |
| Valid event          | Write to Bronze                       | Demonstrated              |
| Duplicate delivery   | Do not create duplicate Bronze record | Demonstrated              |
| Missing `event_time` | Quarantine                            | Demonstrated              |
| Late event           | Detect and log                        | Implemented and exercised |
| RAW ingestion        | Preserve received messages            | Demonstrated              |
| Event traceability   | Preserve partition and offset         | Demonstrated              |

The test is deliberately small enough to reproduce while still exercising realistic streaming concerns.

---

## 26. Validation Evidence

The strongest Day 4 validation evidence is the final ADLS reconciliation:

```text
RAW       = 1,002
Bronze    = 1,000
Quarantine = 1
```

The replay composition was:

```text
999 normal valid records
+ 1 delayed valid record
+ 1 duplicate delivery
+ 1 malformed event
= 1,002 messages
```

The expected processing result was:

```text
1,000 valid logical events
1 duplicate rejected from Bronze
1 malformed event quarantined
```

The final ADLS state matches the expected Bronze and Quarantine counts.

---

## 27. Security and Configuration

Azure credentials and connection strings are stored outside source-controlled code.

The local configuration uses:

```text
.env
```

Relevant variables include:

```text
EVENT_HUB_CONNECTION_STRING
AZURE_STORAGE_CONNECTION_STRING
```

The `.env` file must not be committed to GitHub.

Before running scripts in a new Cloud Shell terminal, environment variables can be loaded using:

```bash
set -a
source .env
set +a
```

Secrets are therefore separated from application code.

---

## 28. Reproducibility

The Day 4 pipeline uses a controlled fixture:

```text
data/fixtures/cdc_sample_1000.json
```

The producer and consumer scripts are stored in the repository:

```text
ingestion/replay/producer.py
ingestion/event_hubs/consumer.py
```

The architecture and validation approach are documented in this file:

```text
docs/day4-cdc-streaming.md
```

The use of a fixed 1,000-record fixture means the core Day 4 test can be reproduced without depending on a continuously changing external API response.

The final production replay should not be rerun against the same validation paths unless a new validation run is intentionally required.

---

## 29. Engineering Outcome

Day 4 demonstrates an end-to-end historical CDC replay architecture using Azure Event Hubs and ADLS Gen2.

The implementation demonstrates:

* event-driven ingestion
* event-time handling
* ingestion-time tracking
* deterministic event IDs
* Event Hubs partitions
* Event Hubs offsets
* RAW landing
* Bronze processing
* duplicate detection
* idempotent processing
* late-event detection
* malformed-event quarantine
* independent storage validation
* operational traceability
* secret separation
* reproducible test fixtures

The architecture deliberately distinguishes between what was successfully validated and what remains incomplete.

In particular:

* ADLS RAW, Bronze, and Quarantine landing was successfully validated.
* Duplicate handling was demonstrated through the controlled replay.
* Late-event detection was implemented and exercised through the deliberately delayed event.
* Synapse connectivity to the project ADLS path was configured and the Bronze path was located, but the current serverless SQL JSON parsing approach did not return usable query rows.

---

## 30. Day 4 Completion Statement

Day 4 successfully demonstrates a controlled historical CDC replay through an Azure event-streaming architecture.

A 1,000-record historical CDC fixture was replayed as 1,002 Event Hub messages containing valid events, one duplicate delivery, one deliberately delayed event, and one malformed event.

The final ADLS validation produced:

```text
RAW        = 1,002
Bronze     = 1,000
Quarantine = 1
```

The pipeline therefore demonstrates the core engineering controls required for a reliable event-ingestion layer:

```text
ingest
  -> preserve
  -> validate
  -> deduplicate
  -> detect late events
  -> quarantine invalid data
  -> reconcile
```

The source is explicitly treated as historical CDC data replayed through a streaming architecture rather than as a live CDC feed.
