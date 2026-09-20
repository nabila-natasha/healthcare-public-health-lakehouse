# ADR-007 — openFDA Batch Ingestion

## Status

Accepted

## Date

2026-09-20

---

## Context

The healthcare lakehouse project requires multiple ingestion patterns to demonstrate how source characteristics influence architecture.

The project has already implemented an Event Hubs-based streaming vertical slice.

A second, genuinely different ingestion pattern is required for a public healthcare API.

openFDA provides healthcare datasets through REST APIs.

The source is accessed by issuing HTTP requests that return a collection of records.

The project therefore needs an ingestion pattern appropriate for a REST-based batch source rather than forcing the source through the existing streaming infrastructure.

---

## Decision

Use Azure Data Factory to ingest openFDA through REST/HTTP into the ADLS Gen2 RAW layer.

The Day 3 ingestion path is:

```text
openFDA REST API
       ↓
Azure Data Factory
       ↓
ADLS Gen2 RAW
       ↓
Python transformation
       ↓
ADLS Bronze
       ↓
Synapse Serverless validation
```

Synapse Serverless is used for validation and querying rather than as the primary ingestion engine.

The Day 3 implementation uses a bounded request:

```text
drug/event.json?limit=100
```

This retrieves 100 adverse-event records for the MVP validation.

---

## Rationale

Azure Data Factory provides:

* REST/HTTP connectivity
* managed orchestration
* monitoring
* retry capabilities
* scheduling
* Azure identity integration
* native integration with Azure storage

This is appropriate for a batch-oriented REST source.

ADF is responsible for the initial source-to-RAW movement.

The subsequent RAW-to-Bronze transformation is implemented separately using Python during development.

This separation keeps source ingestion and transformation as distinct responsibilities.

---

## Actual Day 3 Implementation

The ADF components are:

```text
LS_openFDA_REST
        ↓
DS_openFDA_REST
        ↓
Copy_openFDA_to_RAW
        ↓
DS_openFDA_RAW
```

Pipeline:

```text
PL_openFDA_Batch_Ingestion
```

Actual RAW output:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

The successful execution produced:

```text
Rows read       : 1
Rows copied     : 1
Data read       : 2,700,352 bytes
Data written    : 1,599,087 bytes
Files written   : 1
Copy duration   : 21 seconds
```

The ADF row counts represent the single JSON response document.

The JSON document contains the 100 adverse-event records inside its `results` array.

---

## Bronze Design Decision

The Bronze representation uses the following grain:

```text
One row per safetyreportid
```

The transformation promotes selected scalar and nested attributes into columns.

The current Bronze output contains:

```text
100 rows
17 columns
100 unique safetyreportid
0 duplicate safetyreportid
```

Repeated nested arrays are retained as JSON strings:

```text
reaction[]
drug[]
```

This prevents row multiplication caused by independently expanding both arrays.

A later Silver layer can normalize these structures into child tables if analytical requirements justify that design.

The Bronze transformation was executed during development using Python in Azure Cloud Shell.

The transformation code is maintained in GitHub.

Full automated RAW-to-Bronze orchestration is deferred to a later project phase.

---

## Why Not Event Hubs?

Event Hubs is designed for event streaming.

The openFDA API does not provide the project with an operational Kafka/Event Hubs event stream.

Introducing Event Hubs between openFDA and the lakehouse would therefore add an unnecessary transport layer.

The project instead uses:

```text
openFDA
   ↓
HTTP
   ↓
ADF
```

for the batch workload.

Event Hubs remains part of the separate CDC streaming simulation.

---

## CDC Dataset Distinction

The project uses the COVID-19 Case Surveillance Public Use Data with Geography as a real public-health dataset.

That dataset is not represented as an operational Kafka/Event Hubs source.

Instead, historical CDC records are replayed through a Python producer to simulate a streaming ingestion workload.

Therefore:

```text
Real source data
        +
Simulated streaming transport
```

is explicitly distinguished from:

```text
Real operational event stream
```

The project will not claim that the CDC public-use dataset itself is a Kafka/Event Hubs stream.

---

## Consequences

### Positive

* Demonstrates multiple ingestion patterns.
* Uses ADF for an appropriate Azure batch workload.
* Preserves source data in RAW.
* Separates ingestion from transformation.
* Creates a clear architectural comparison with Event Hubs.
* Uses a real external healthcare API rather than synthetic batch data.
* Provides a foundation for incremental ingestion.
* Demonstrates source-driven schema design.
* Provides reproducible SQL validation of the Bronze output.

### Negative

The first implementation is intentionally limited.

It does not initially implement:

* complete API pagination
* incremental extraction
* metadata-driven ingestion
* automated failure notifications
* production scheduling
* automated RAW-to-Bronze orchestration
* complete Bronze/Silver/Gold transformation
* production-grade historical batch partitioning

These are deferred to later stages.

---

## Future Evolution

The pipeline can later be extended with:

```text
API
 ↓
ADF
 ↓
pagination
 ↓
watermark / incremental logic
 ↓
run-specific RAW
 ↓
Bronze
 ↓
Silver
 ↓
Gold
```

Additional production improvements could include:

```text
ADF
 ↓
retry / failure handling
 ↓
metadata logging
 ↓
data-quality validation
 ↓
monitoring / alerting
 ↓
CI/CD deployment
```

The initial Day 3 implementation prioritizes proving the ingestion path before adding production-level complexity.

---

## Validation Evidence

The implementation is validated through:

```text
ADF execution
        ↓
ADLS RAW validation
        ↓
Python Bronze transformation
        ↓
Bronze uniqueness validation
        ↓
Synapse Serverless SQL validation
```

The SQL validation script is maintained at:

```text
sql/validation/day3_openfda_validation.sql
```

Key validation results:

```text
Source records          : 100
Unique safetyreportid   : 100
Duplicate IDs           : 0
Bronze rows             : 100
Bronze columns          : 17
Synapse rows            : 100
Synapse distinct IDs    : 100
Synapse duplicate IDs   : 0
```

---

## Final Decision

For Day 3, openFDA is treated as a **batch REST source** and ingested directly through Azure Data Factory into ADLS RAW.

The project deliberately keeps the openFDA batch path separate from the Event Hubs streaming simulation.

This architecture is based on the characteristics of the source rather than on a requirement to use one ingestion technology for every dataset.
