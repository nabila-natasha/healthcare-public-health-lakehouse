# Data Sources

## openFDA

### Source

openFDA

### Domain

Healthcare / pharmaceutical safety

### Dataset

FDA adverse event data

### Access pattern

REST/HTTP API

### Ingestion pattern

Batch

### Azure component

Azure Data Factory

### Destination

ADLS Gen2 RAW

```text
healthcare/raw/openfda/
```

### API request

The Day 3 MVP uses the openFDA adverse-event endpoint with a bounded request:

```text
drug/event.json?limit=100
```

The bounded request is intentional. The purpose of Day 3 is to prove the ingestion architecture rather than retrieve the complete source dataset.

### Why batch?

The source is accessed by explicitly requesting a collection of records from a REST API.

The project therefore treats the source as a batch workload rather than an operational event stream.

The ingestion flow is:

```text
openFDA REST API
      ↓
ADF Copy Activity
      ↓
ADLS RAW
```

### Day 3 implementation

The initial implementation successfully retrieved a response containing:

```text
100 adverse-event records
```

The ADF Copy Activity wrote one JSON document to ADLS RAW.

Important distinction:

```text
ADF rows read/copied = 1 JSON document
openFDA records      = 100 adverse-event records
```

The JSON response contains the records inside the `results` array.

### RAW output

Actual Day 3 RAW path:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

Actual file size:

```text
1,599,087 bytes
```

### Bronze representation

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

are retained as JSON strings to avoid creating a reaction × drug row multiplication at the Bronze layer.

### Source quality observations

The source was inspected before finalizing the Bronze representation.

For the 100 retrieved records:

```text
safetyreportid missing       : 0
transmissiondate missing     : 0
receivedate missing          : 0
receiptdate missing          : 0
duplicate safetyreportid     : 0
```

The source also contained missing values for some optional fields. For example:

```text
seriousnessdeath missing     : 96 / 100
```

Missing values are preserved as NULL rather than being interpreted as a negative value.

### Future enhancements

Future enhancements may include:

* API pagination
* incremental extraction
* watermarking
* run-specific or date-partitioned RAW paths
* scheduling
* retry handling
* failure notifications
* metadata-driven ingestion
* schema-drift detection
* automated RAW-to-Bronze orchestration

---

# CDC COVID-19 Case Surveillance Public Use Data with Geography

### Source

Centers for Disease Control and Prevention public-use COVID-19 case surveillance data.

### Domain

Public health / COVID-19 case surveillance

### Role in project

Real public-health source dataset for the project's streaming simulation.

### Access pattern

Historical public-use dataset.

### Project ingestion pattern

Simulated streaming.

### Transport

Azure Event Hubs using Kafka-compatible connectivity.

### Producer

Python replay producer.

### Consumer

Python Event Hubs/Kafka consumer.

### Destination

ADLS Gen2:

```text
healthcare/raw/cdc/
```

and:

```text
healthcare/bronze/cdc/
```

### Important architectural distinction

The CDC public-use dataset is real source data.

The project does not claim that the CDC dataset itself is an operational Kafka/Event Hubs event stream.

Instead, historical source records are replayed as individual events to simulate a streaming workload.

The architecture is:

```text
Historical CDC records
        ↓
Python replay producer
        ↓
Azure Event Hubs
        ↓
Python consumer
        ↓
ADLS RAW
        ↓
Bronze
```

This allows the project to demonstrate:

* event ingestion
* event time
* ingestion time
* duplicate detection
* event IDs
* consumer processing
* RAW landing
* Bronze processing
* streaming architecture

without misrepresenting the characteristics of the public dataset.

### Streaming simulation limitation

The Event Hubs stream represents a **simulated transport layer**.

It should therefore be described in the portfolio as:

```text
Real public-health data
+
Simulated streaming transport
```

rather than:

```text
Real operational healthcare event stream
```

This distinction is maintained throughout the project documentation.
