# ADR-002: Use Azure Event Hubs for the Streaming Transport Layer

**Status:** Accepted  
**Date:** 2026-09-21  
**Decision owners:** Project implementation team  

---

## Context

Day 4 requires the project to demonstrate event-driven ingestion using real historical public-health records.

The CDC source is not itself a live event stream.

The project therefore needs a streaming transport that can receive historical records as individual events while preserving streaming concepts such as:

* event IDs
* event time
* ingestion time
* partitions
* offsets
* consumer groups
* duplicate delivery
* replay
* late-event detection

---

## Decision

Use **Azure Event Hubs** as the event-ingestion and transport layer.

The project uses:

```text
Event Hubs Namespace:
eh-lakehouse-bello

Event Hub:
healthcare-events
```

Configuration:

```text
Partitions : 4
Retention  : 7 days
```

---

## Architecture

```text
Historical CDC Dataset
        ↓
Python Replay Producer
        ↓
Azure Event Hubs
        ↓
Python Streaming Consumer
        ↓
ADLS Gen2
```

The Event Hub therefore acts as the transport boundary between the replay producer and the downstream consumer.

---

## Why Event Hubs?

Event Hubs provides the concepts required for the streaming demonstration:

* event ingestion
* partitioning
* offsets
* consumer groups
* retention
* replay-oriented consumption
* Kafka-compatible connectivity

The project also previously validated Kafka connectivity against the Event Hubs environment.

---

## Partitioning

The Event Hub contains:

```text
4 partitions
```

Partitions provide independent logical event streams.

An event is associated with:

```text
partition
offset
```

The offset is relative to the individual partition.

Therefore:

```text
partition 0, offset 1206
```

does not mean that 1,206 messages were globally sent to the Event Hub.

---

## Consumer groups

The final Day 4 validation used:

```text
healthcare-bronze-consumer-day4-final-20260921
```

Consumer groups allow independent consumers to maintain separate consumption state.

This is important when multiple downstream processing applications need to consume the same event stream independently.

---

## Historical replay model

The CDC source is historical.

The Event Hub therefore does not represent a live CDC feed.

Instead:

```text
Real historical CDC records
        ↓
Controlled replay producer
        ↓
Event Hubs
```

This creates a controlled event-streaming test environment.

---

## Day 4 validation

The final replay produced:

```text
1,002 Event Hub messages
```

The composition was:

```text
999 normal valid records
+ 1 deliberately delayed valid record
+ 1 duplicate delivery
+ 1 malformed event
= 1,002 messages
```

The downstream ADLS validation produced:

```text
RAW        = 1,002
Bronze     = 1,000
Quarantine = 1
```

---

## Alternatives considered

### Kafka

Kafka would provide a strong event-streaming platform and was relevant to the project's learning objectives.

However, introducing a separate Kafka cluster would add operational complexity and infrastructure requirements.

Event Hubs provides Kafka-compatible connectivity while remaining within the Azure architecture.

### Azure Service Bus

Service Bus is better suited to enterprise messaging patterns such as queues, commands, and transactional messaging.

The project requires partitioned event-stream processing rather than queue-oriented enterprise messaging.

### Direct ADLS ingestion

Directly writing CDC records to ADLS would simplify the pipeline but would not demonstrate:

* partitions
* offsets
* consumer groups
* streaming delivery
* duplicate delivery
* event-level processing

---

## Consequences

### Positive

* Native Azure streaming service
* Partition-based event ingestion
* Consumer-group support
* Retention and replay capabilities
* Kafka-compatible connectivity
* Strong fit with the project's Azure architecture

### Trade-offs

* Event Hubs introduces another managed Azure resource.
* Retention is finite.
* Long-term replay requires durable storage such as ADLS.
* Event-level state and idempotency still need to be designed by consumers.

---

## Production evolution

A production architecture could introduce:

* managed checkpointing
* durable idempotency state
* monitoring and alerting
* schema governance
* dead-letter/quarantine monitoring
* autoscaling consumers
* partition-key optimization
* consumer lag monitoring
* automated operational runbooks

The current implementation intentionally demonstrates these concepts at portfolio scale without claiming a production-grade managed streaming platform.


