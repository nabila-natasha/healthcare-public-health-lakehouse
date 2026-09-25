# ADR-004: Controlled Replay vs Live API Consumption

**Status:** Accepted  
**Date:** 2026-09-21  
**Decision owners:** Project implementation team  

---

## Context

The project needs to demonstrate streaming ingestion using public-health data.

The CDC source is an archived historical dataset.

The engineering team therefore had two possible approaches:

1. call the external API continuously during the streaming test
2. retrieve a controlled dataset and replay the records through the streaming architecture

---

## Decision

Use **controlled replay from a fixed CDC fixture** for the Day 4 streaming implementation.

The fixture is:

```text
data/fixtures/cdc_sample_1000.json
```

It contains:

```text
1,000 source records
```

The records are replayed through:

```text
Python producer
      ↓
Azure Event Hubs
      ↓
Python consumer
      ↓
ADLS
```

---

## Rationale

### Reproducibility

A fixed fixture ensures that the same source records can be replayed repeatedly.

This is important when testing:

* duplicate handling
* malformed records
* late events
* consumer behavior
* reconciliation

---

### Deterministic validation

The final test deliberately creates:

```text
999 normal valid records
+ 1 delayed valid record
+ 1 duplicate delivery
+ 1 malformed event
= 1,002 messages
```

A live external API would make it harder to guarantee the exact same input composition.

---

### Independence from source changes

External public APIs can change their available records, metadata, or responses.

Using a fixture means the core streaming test is not dependent on the external API remaining unchanged.

---

### Safe failure testing

The project intentionally introduces a malformed event.

It would not be appropriate to modify the external CDC source.

The fixture provides a safe way to introduce controlled test faults.

---

### Separation of concerns

The project separates:

```text
Source ingestion
```

from:

```text
Streaming engineering validation
```

This allows the event-processing architecture to be tested independently of source API availability.

---

## Why not continuously call the live API?

The CDC source is historical and archived.

It does not provide the type of continuously emitted operational event stream that would justify treating the API as a live streaming producer.

Repeatedly polling the API would therefore simulate polling rather than demonstrate a genuine event stream.

The project instead makes the simulation explicit:

```text
Historical CDC data
+
Controlled replay
=
Streaming test workload
```

---

## Replay fault injection

The replay intentionally introduces:

### Duplicate delivery

One valid event is sent twice.

Expected behavior:

```text
Same event_id
        ↓
Duplicate detected
        ↓
No second Bronze record
```

### Malformed event

One event is missing:

```text
event_time
```

Expected behavior:

```text
Validation failure
        ↓
Quarantine
```

### Delayed event

One valid event is deliberately delayed.

Expected behavior:

```text
event_time arrives out of order
        ↓
Late-event detection
```

---

## Day 4 result

The final replay produced:

```text
1,002 Event Hub messages
```

ADLS validation produced:

```text
RAW        = 1,002
Bronze     = 1,000
Quarantine = 1
```

The result reconciles with the expected message composition.

---

## Alternatives considered

### Live API polling

Rejected for the Day 4 validation workload because the source is historical and the test requires deterministic event behavior.

### Generate completely synthetic CDC records

Rejected because using real CDC records provides stronger source realism.

### Replay the entire CDC dataset

Rejected for the controlled engineering test because it would increase runtime, storage, and operational complexity without materially improving the demonstration of the streaming controls.

---

## Consequences

### Positive

* Reproducible testing
* Controlled fault injection
* Deterministic validation
* Reduced dependency on external API availability
* Real source data retained
* Easier debugging

### Trade-offs

* Replay is not equivalent to a live operational source.
* The fixture must be refreshed deliberately if the source characteristics need to be updated.
* The project does not demonstrate live source-to-event-producer integration.

---

## Production evolution

If the project were connected to a genuine operational public-health event source, the replay layer could be replaced by a real producer or CDC connector.

The target architecture would become:

```text
Operational Source
        ↓
Event Producer / CDC Connector
        ↓
Azure Event Hubs
        ↓
Streaming Consumer
        ↓
ADLS
```

The current replay producer therefore acts as a controlled stand-in for the upstream producer rather than being presented as a production CDC connector.

---

## Decision summary

The Day 4 architecture intentionally chooses:

```text
Real historical source
        +
Controlled replay
        +
Real Azure streaming infrastructure
```

rather than claiming:

```text
Live CDC source
        +
Real-time healthcare event feed
```

This provides a reproducible engineering demonstration while keeping the project's claims aligned with the actual source and implementation.


