# ADR-003: Batch vs Streaming Ingestion Strategy

**Status:** Accepted
**Date:** 2026-09-21
**Decision owners:** Project implementation team

---

## Context

The healthcare/public-health lakehouse contains multiple external data sources with different source characteristics.

The project currently uses:

1. openFDA adverse-event data
2. historical CDC public-health surveillance data

These sources should not automatically be forced into the same ingestion pattern.

The architectural question is:

> Should all external data be ingested through streaming, or should the ingestion pattern reflect the characteristics of each source?

---

## Decision

Use **batch ingestion for openFDA** and **simulated streaming ingestion for the historical CDC dataset**.

The resulting architecture is:

```text
openFDA
REST API
   ↓
ADF Batch Ingestion
   ↓
ADLS RAW
   ↓
Bronze
```

and:

```text
Historical CDC Dataset
   ↓
Controlled Replay
   ↓
Event Hubs
   ↓
Streaming Consumer
   ↓
ADLS RAW
   ↓
Bronze / Quarantine
```

---

## Rationale

### openFDA

openFDA is accessed through an HTTP API where the client requests a collection of records.

The Day 3 implementation used:

```text
drug/event.json?limit=100
```

This is naturally represented as a batch extraction.

There is no reason to introduce an event-streaming layer simply because the overall platform supports streaming.

---

### CDC

The CDC dataset used by Day 4 is historical.

The source itself is therefore not a live operational event stream.

However, the project needs to demonstrate event-driven ingestion engineering.

The historical records are therefore replayed through Event Hubs.

This allows the project to demonstrate:

* event envelopes
* event time
* ingestion time
* deterministic event IDs
* duplicate delivery
* partitions
* offsets
* consumer groups
* late-event detection
* malformed-event quarantine

without misrepresenting the source as a live stream.

---

## Source vs transport distinction

The project deliberately separates:

```text
Source type
```

from:

```text
Ingestion transport
```

For CDC:

```text
Source:
historical public-health dataset

Transport:
simulated event stream
```

Therefore:

```text
Historical source
≠
live streaming source
```

This distinction is important for architectural accuracy.

---

## Day 4 evidence

The controlled CDC replay produced:

```text
1,002 Event Hub messages
```

The final ADLS validation was:

```text
RAW        = 1,002
Bronze     = 1,000
Quarantine = 1
```

This demonstrates that the streaming architecture can process a historical dataset while preserving event-level operational controls.

---

## Alternatives considered

### Stream everything

This would create unnecessary complexity for REST-based batch sources.

It would also incorrectly imply that openFDA is an operational event stream.

### Batch everything

This would simplify the platform but would prevent the project from demonstrating event-driven ingestion concepts.

### Use separate platforms for every source

This would make the architecture unnecessarily fragmented.

The chosen design instead uses the same lakehouse storage platform while allowing each source to use the ingestion pattern appropriate to its characteristics.

---

## Consequences

### Positive

* Source characteristics are respected.
* Architecture avoids unnecessary streaming.
* Streaming engineering can still be demonstrated.
* The platform supports both batch and event-driven workloads.
* The design is easier to explain to stakeholders.

### Trade-offs

* Two ingestion patterns must be maintained.
* Streaming requires additional operational concepts.
* Historical replay is not equivalent to real-time source integration.

---

## Production evolution

If a genuine operational CDC/event source becomes available, the CDC ingestion path could evolve from:

```text
Historical source
↓
Replay
↓
Event Hubs
```

to:

```text
Operational source
↓
Event producer / CDC connector
↓
Event Hubs
↓
Streaming consumer
```

The downstream lakehouse layers could remain largely consistent.

