# Day 3 — openFDA Batch Ingestion

## 1. Objective

Day 3 implements the first real external healthcare data ingestion pipeline.

The objective is to demonstrate a production-oriented batch ingestion pattern using a public healthcare API:

```text
openFDA REST API
       │
       ▼
Azure Data Factory
       │
       ▼
ADLS Gen2 — RAW
       │
       ▼
Bronze
       │
       ▼
Synapse Serverless validation
```

The pipeline is intentionally separate from the Event Hubs streaming pipeline implemented during Day 2.

The Day 3 focus is **batch ingestion**, not downstream analytics or machine learning.

---

# 2. Business and Engineering Context

Healthcare data platforms commonly receive data through different ingestion patterns.

A source may expose:

* REST APIs
* files
* databases
* message queues
* event streams
* change-data-capture feeds

The ingestion architecture should therefore be determined by the characteristics of the source rather than forcing every source into the same transport mechanism.

For this project:

| Source                       | Ingestion pattern   | Transport        | Orchestration            |
| ---------------------------- | ------------------- | ---------------- | ------------------------ |
| openFDA                      | Batch               | REST/HTTP        | Azure Data Factory       |
| CDC COVID-19 public-use data | Simulated streaming | Event Hubs/Kafka | Python producer/consumer |

This distinction is intentional.

The CDC dataset is real public-health data, while its Event Hubs transport is simulated for portfolio purposes.

---

# 3. Source

## 3.1 Source system

**openFDA**

openFDA provides public access to U.S. Food and Drug Administration datasets through REST APIs.

For Day 3, the project uses the FDA adverse-event API.

The source is accessed through an HTTP request and returns a bounded response containing healthcare-related records.

The Day 3 request retrieves:

```text
100 adverse-event records
```

---

## 3.2 Why openFDA is treated as a batch source

The pipeline initiates an HTTP request to retrieve a collection of records.

The source is therefore consumed as a batch rather than as an operational event stream.

The ingestion process is:

```text
API request
    │
    ▼
bounded response
    │
    ▼
ADF Copy Activity
    │
    ▼
ADLS RAW
```

The pipeline can subsequently be scheduled to execute periodically.

For example:

```text
Every hour
Every 6 hours
Daily
```

depending on the business requirement.

The exact schedule is not required for the Day 3 MVP.

---

# 4. Architecture

## 4.1 Day 3 architecture

```text
                         BATCH INGESTION

                    ┌──────────────────┐
                    │     openFDA      │
                    │    REST API      │
                    └────────┬─────────┘
                             │
                             │ HTTPS
                             ▼
                    ┌──────────────────┐
                    │ Azure Data       │
                    │ Factory          │
                    │                  │
                    │ Copy Activity    │
                    └────────┬─────────┘
                             │
                             │ Managed Identity
                             ▼
                    ┌──────────────────┐
                    │ ADLS Gen2        │
                    │                  │
                    │ healthcare/      │
                    │   raw/openfda/   │
                    └────────┬─────────┘
                             │
                             │ Python transformation
                             ▼
                    ┌──────────────────┐
                    │ Bronze           │
                    │                  │
                    │ Structured /     │
                    │ validated        │
                    │ representation   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Synapse          │
                    │ Serverless SQL   │
                    │                  │
                    │ Validation       │
                    └──────────────────┘
```

---

# 5. Azure Resources Used

Day 3 reuses the infrastructure created during Days 0–2.

| Resource                 | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `rg-lakehouse-portfolio` | Resource group                               |
| `stlakehousebello`       | Primary ADLS Gen2 data lake                  |
| `healthcare`             | ADLS filesystem                              |
| `adf-lakehouse-bello`    | Batch ingestion/orchestration                |
| `syn-lakehouse-bello`    | Serverless SQL validation                    |
| `eh-lakehouse-bello`     | Streaming infrastructure used by Day 2/Day 4 |
| `healthcare-events`      | Event Hubs stream used for CDC simulation    |

The Event Hubs resources are not part of the Day 3 batch path.

---

# 6. ADLS Data-Lake Layout

The project uses the following logical layers:

```text
stlakehousebello
└── healthcare/

    ├── raw/
    │   ├── openfda/
    │   └── cdc/

    ├── bronze/
    │   ├── openfda/
    │   └── cdc/

    ├── silver/

    ├── gold/

    └── quarantine/
```

Day 3 primarily uses:

```text
raw/openfda/
bronze/openfda/
```

---

# 7. RAW Layer

The RAW layer is the source landing zone.

Its purpose is to preserve the source data with minimal transformation.

The RAW layer supports:

* source traceability
* replayability
* auditability
* debugging
* ingestion troubleshooting
* downstream reprocessing

The RAW layer should not be treated as the final analytical layer.

For this MVP, ADF writes the openFDA API response as a JSON file.

Actual RAW output:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

File size:

```text
1,599,087 bytes
```

---

# 8. RAW Storage Convention

The actual Day 3 MVP uses:

```text
raw/openfda/openfda_adverse_events.json
```

This is a simple fixed-path implementation used to prove the ingestion pattern.

For repeated production ingestion, a run-specific or partitioned convention would be preferable, for example:

```text
raw/openfda/
└── ingestion_date=YYYY-MM-DD/
    └── <batch output>
```

The purpose of such a convention would be to prevent subsequent ingestion runs from unintentionally overwriting historical batches.

This is a future enhancement rather than part of the current Day 3 implementation.

---

# 9. Bronze Layer

Bronze represents the first structured and validated representation of the source data.

For the Day 3 MVP, the Bronze transformation uses:

```text
One row = one safetyreportid
```

The observed source contained:

```text
Input records             : 100
Unique safetyreportid     : 100
Duplicate safetyreportid  : 0
```

The Bronze output contains:

```text
Rows       : 100
Columns    : 17
```

The Bronze file is:

```text
healthcare/bronze/openfda/openfda_adverse_events.csv
```

File size:

```text
1,676,791 bytes
```

## 9.1 Bronze schema approach

The transformation promotes selected scalar and nested attributes into columns.

The current 17-column representation includes:

```text
safetyreportid
transmissiondate
receivedate
receiptdate
serious
seriousnessdeath
fulfillexpeditecriteria
companynumb
reportercountry
reporterqualification
senderorganization
patientonsetage
patientonsetageunit
patientsex
patientdeathdate
reactions_json
drugs_json
```

Repeated arrays such as:

```text
reaction[]
drug[]
```

are retained as JSON strings.

This avoids creating a reaction × drug row multiplication at the Bronze layer.

A later Silver model can normalize these nested structures into separate child tables if analytical requirements justify doing so.

---

## 9.2 Source-driven schema design

The Bronze schema was finalized after inspecting the actual openFDA response.

This is deliberate.

A data engineer should inspect the source before finalizing the downstream schema rather than assuming the source structure in advance.

For example, the source showed that:

```text
seriousnessdeath
```

was missing in:

```text
96 of 100 records
```

The transformation therefore preserves those missing values as NULL rather than incorrectly converting them to zero.

---

# 10. Data Lineage

The actual Day 3 lineage is:

```text
openFDA
   │
   │ HTTPS
   ▼
ADF REST Dataset
   │
   │ Copy Activity
   ▼
ADLS RAW
   │
   │ Python transformation
   ▼
ADLS Bronze
   │
   │ SQL query
   ▼
Synapse Serverless
```

Each stage has a distinct responsibility.

| Layer                 | Responsibility                         |
| --------------------- | -------------------------------------- |
| openFDA               | Source system                          |
| ADF                   | Batch ingestion/orchestration          |
| RAW                   | Source-preserving landing              |
| Python transformation | Initial structuring/validation         |
| Bronze                | Structured report-level representation |
| Synapse               | Query and validation                   |

The RAW-to-Bronze transformation was executed during development using Python in Azure Cloud Shell.

The transformation code is maintained in GitHub.

Full automated orchestration of RAW-to-Bronze is a future enhancement.

---

# 11. Azure Data Factory Components

The Day 3 implementation uses:

## Linked service

```text
LS_openFDA_REST
```

Purpose:

Connect ADF to the public openFDA REST API.

Authentication:

```text
Anonymous
```

The API is publicly accessible and does not require an Azure identity.

---

## ADLS linked service

```text
LS_ADLS_healthcare
```

Purpose:

Connect ADF to the project ADLS Gen2 account.

Authentication:

```text
Managed Identity
```

The ADF managed identity has:

```text
Storage Blob Data Contributor
```

on the project storage account.

This avoids embedding a storage account key in the ADF pipeline.

---

## REST dataset

```text
DS_openFDA_REST
```

Purpose:

Represent the openFDA REST endpoint consumed by ADF.

The configured request is:

```text
drug/event.json?limit=100
```

---

## RAW dataset

```text
DS_openFDA_RAW
```

Purpose:

Represent the ADLS destination for the raw openFDA response.

Destination:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

---

## Pipeline

```text
PL_openFDA_Batch_Ingestion
```

Purpose:

Execute the HTTP-to-ADLS batch ingestion.

---

# 12. Expected Pipeline Flow

```text
PL_openFDA_Batch_Ingestion
            │
            ▼
       REST source
            │
            ▼
       Copy Activity
            │
            ▼
       ADLS RAW/openfda
```

The first implementation intentionally uses a bounded request.

The request retrieves:

```text
100 records
```

Pagination and incremental extraction are future enhancements rather than Day 3 requirements.

---

# 13. Why Azure Data Factory?

Azure Data Factory is used because the source is an external REST API and the project requires managed batch orchestration.

ADF provides:

* managed connectors
* pipeline orchestration
* retry capabilities
* monitoring
* scheduling
* activity-level execution information
* integration with Azure identity and storage

This also gives the project a clear contrast with the Event Hubs streaming architecture.

---

# 14. Why Event Hubs Is Not Used for openFDA

The project does not place openFDA behind Event Hubs merely to make every source look like a streaming source.

The source characteristics are different.

openFDA is accessed through a REST API.

Therefore:

```text
openFDA
   ↓
HTTP
   ↓
ADF
```

is the direct Day 3 ingestion pattern.

Event Hubs is reserved for the project's streaming simulation.

---

# 15. Relationship to the CDC Dataset

The project also uses the **COVID-19 Case Surveillance Public Use Data with Geography** as a real public-health dataset.

The CDC dataset has a different role.

It will be used as the source data for the project's streaming simulation.

The architecture is:

```text
CDC public-use dataset
        │
        ▼
Historical source records
        │
        ▼
Python replay producer
        │
        ▼
Azure Event Hubs
        │
        ▼
Python consumer
        │
        ▼
ADLS RAW
        │
        ▼
Bronze
```

The distinction is important:

> The CDC dataset is real public data, but the Event Hubs stream is simulated.

The project does not claim that the CDC public-use dataset itself is an operational Kafka or Event Hubs stream.

---

# 16. Event-Time and Ingestion-Time Concepts

The streaming pipeline will distinguish:

```text
event_time
```

from:

```text
ingestion_time
```

`event_time` represents the time associated with the source event.

`ingestion_time` represents the time at which the platform receives the event.

This allows the project to calculate or analyze ingestion latency:

```text
latency = ingestion_time - event_time
```

This concept is not required for the Day 3 batch pipeline but remains part of the overall project data architecture.

---

# 17. Data Quality Considerations

Day 3 does not implement the complete project-wide data-quality framework.

However, the batch pipeline validates:

### Availability

The openFDA source was reachable and returned data.

### Pipeline execution

ADF completed successfully.

```text
Status: Succeeded
```

### File existence

The expected RAW file was created.

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

### Record presence

The response contained:

```text
100 records
```

### Uniqueness

The source contained:

```text
100 unique safetyreportid
0 duplicate safetyreportid
```

### Required fields

The following required fields had zero missing values:

```text
safetyreportid
transmissiondate
receivedate
receiptdate
```

### Schema inspection

The JSON response was inspected before defining the Bronze representation.

### Missing-value handling

`seriousnessdeath` was missing in 96 of 100 records and was retained as NULL rather than interpreted as zero.

### Synapse validation

Synapse confirmed:

```text
bronze_row_count       = 100
distinct_report_count  = 100
duplicate_report_count = 0
```

---

# 18. Validation Evidence

The following evidence should be captured for the final portfolio record.

## Evidence 1 — ADF pipeline

Screenshot showing:

```text
PL_openFDA_Batch_Ingestion
```

and its Copy Activity.

---

## Evidence 2 — Successful execution

ADF Monitor should show:

```text
Status: Succeeded
```

Execution date:

```text
2026-09-20
```

---

## Evidence 3 — Activity statistics

Capture the Copy Activity output containing:

```text
rowsRead
rowsCopied
dataRead
dataWritten
filesWritten
copyDuration
```

Actual values:

```text
rowsRead     : 1
rowsCopied   : 1
dataRead     : 2,700,352 bytes
dataWritten  : 1,599,087 bytes
filesWritten : 1
duration     : 21 seconds
```

The `rowsRead` and `rowsCopied` values represent one JSON document, not one adverse-event record.

---

## Evidence 4 — ADLS output

Verify:

```text
healthcare/raw/openfda/
```

contains:

```text
openfda_adverse_events.json
```

---

## Evidence 5 — Sample data

Inspect a sample of the landed openFDA records.

The sample demonstrated real FDA adverse-event fields including:

```text
safetyreportid
transmissiondate
receivedate
receiptdate
serious
primarysource
patient
reaction
drug
```

---

## Evidence 6 — Bronze output

Verify:

```text
healthcare/bronze/openfda/
```

contains:

```text
openfda_adverse_events.csv
```

with:

```text
100 rows
17 columns
100 unique safetyreportid
0 duplicate safetyreportid
```

---

## Evidence 7 — Query validation

Use Synapse Serverless to confirm that the Bronze data can be accessed.

The validation SQL is maintained in:

```text
sql/validation/day3_openfda_validation.sql
```

---

# 19. Execution Record

### Pipeline

```text
PL_openFDA_Batch_Ingestion
```

### Execution date

```text
2026-09-20
```

### Run status

```text
Succeeded
```

### Source

```text
openFDA
```

### Dataset

```text
FDA adverse event data
```

### Requested records

```text
100
```

### Rows read

```text
1
```

### Rows copied

```text
1
```

These values represent the single JSON response document handled by the ADF Copy Activity.

The JSON document contained 100 adverse-event records.

### Data read

```text
2,700,352 bytes
```

### Data written

```text
1,599,087 bytes
```

### Files written

```text
1
```

### Copy duration

```text
21 seconds
```

### Integration runtime

```text
AutoResolveIntegrationRuntime (Southeast Asia)
```

### RAW path

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

### RAW file size

```text
1,599,087 bytes
```

### Bronze path

```text
healthcare/bronze/openfda/openfda_adverse_events.csv
```

### Bronze file size

```text
1,676,791 bytes
```

### Bronze rows

```text
100
```

### Bronze columns

```text
17
```

### Bronze uniqueness validation

```text
Unique safetyreportid   : 100
Duplicate IDs           : 0
```

### Synapse validation

```text
bronze_row_count       = 100
distinct_report_count  = 100
duplicate_report_count = 0
```

---

# 20. Day 3 Validation Table

| Validation              | Expected   | Actual                    | Result  |
| ----------------------- | ---------- | ------------------------- | ------- |
| REST source reachable   | Yes        | Yes                       | PASS    |
| ADF pipeline created    | Yes        | Yes                       | PASS    |
| ADF execution           | Succeeded  | Succeeded                 | PASS    |
| RAW output created      | Yes        | Yes                       | PASS    |
| RAW file non-empty      | Yes        | 1,599,087 bytes           | PASS    |
| Source records present  | Yes        | 100                       | PASS    |
| Unique report IDs       | 100        | 100                       | PASS    |
| Duplicate report IDs    | 0          | 0                         | PASS    |
| Required fields missing | 0          | 0                         | PASS    |
| Bronze output created   | Yes        | Yes                       | PASS    |
| Bronze rows             | 100        | 100                       | PASS    |
| Bronze columns          | 17         | 17                        | PASS    |
| Synapse validation      | Successful | 100 / 100 / 0             | PASS    |
| Evidence captured       | Yes        | Pending final screenshots | PENDING |

---

# 21. Security

The Day 3 implementation follows the principle of minimizing embedded credentials.

The openFDA REST API is public and therefore does not require a secret.

ADLS access is performed using the ADF managed identity rather than embedding a storage account connection string in the pipeline.

The project therefore avoids storing Azure storage credentials in GitHub.

Secrets must not be committed to:

* Git
* GitHub
* README files
* Markdown documentation
* ADF JSON definitions

---

# 22. Limitations

The Day 3 implementation intentionally has a limited scope.

### Bounded API request

The first implementation retrieves a bounded set of:

```text
100 records
```

rather than attempting to retrieve the entire openFDA dataset.

### Pagination

API pagination is not required for the Day 3 MVP.

### Incremental loading

A production incremental strategy has not yet been implemented.

### RAW file naming

The MVP uses a fixed output filename.

Repeated production ingestion should use run-specific or partitioned paths to preserve historical batches.

### Automated RAW-to-Bronze orchestration

The Bronze transformation is currently executed through Python during development rather than being fully orchestrated by ADF.

### CSV Bronze representation

CSV was selected for the MVP because it makes the transformed data easy to inspect and validate.

A production analytical implementation could use Parquet or another columnar format.

### Full Bronze-to-Silver modelling

The complete Bronze-to-Silver data model is outside the Day 3 scope.

### Production scheduling

The pipeline is proven manually before introducing scheduled execution.

These limitations are intentional so that the ingestion pattern can be validated before adding complexity.

---

# 23. Future Improvements

Potential improvements include:

1. API pagination.
2. Incremental extraction.
3. Run-specific or date-partitioned RAW paths.
4. Retry policies.
5. Failure notifications.
6. Metadata-driven ingestion.
7. Source watermarking.
8. Data-quality rules.
9. Schema drift detection.
10. Bronze-to-Silver PySpark processing.
11. Automated RAW-to-Bronze orchestration.
12. Pipeline CI/CD deployment.

These enhancements belong to later project phases.

---

# 24. Day 3 Gate

The technical Day 3 gate has been passed when the following are complete:

```text
[x] openFDA REST source configured
[x] ADF REST linked service validated
[x] ADLS linked service validated
[x] ADF batch pipeline created
[x] ADF pipeline executed successfully
[x] openFDA data landed in ADLS RAW
[x] Sample records inspected
[x] Bronze transformation completed
[x] Synapse validation completed
[x] No secrets committed
```

Repository and evidence packaging:

```text
[ ] Evidence screenshots captured
[ ] Documentation updated
[ ] SQL validation script committed
[ ] Changes committed to Git
[ ] Feature branch pushed
[ ] Changes merged to main
```

Current status:

```text
TECHNICAL PIPELINE: PASS
DOCUMENTATION: UPDATED
REPOSITORY PACKAGING: IN PROGRESS
```

The Day 3 gate becomes fully complete after the evidence and Git steps above are completed.

---

# 25. Day 3 Conclusion

Day 3 demonstrates that the lakehouse can ingest a real external healthcare API through a managed batch pipeline.

The implementation intentionally complements rather than duplicates the Day 2 streaming architecture.

The resulting project demonstrates two different ingestion patterns:

```text
                 HEALTHCARE DATA PLATFORM

       ┌──────────────────┐
       │     openFDA      │
       │    REST API      │
       └────────┬─────────┘
                │
              BATCH
                │
                ▼
               ADF
                │
                ▼
               RAW
                │
                ▼
             BRONZE
                │
                ▼
            SYNAPSE


       ┌──────────────────────┐
       │ CDC public-use data  │
       └──────────┬───────────┘
                  │
           replay/simulation
                  │
                  ▼
             Event Hubs
                  │
                  ▼
                RAW
                  │
                  ▼
               BRONZE
```

This separation reflects the source characteristics rather than forcing a single ingestion technology onto every source.

Day 3 therefore adds a second ingestion pattern to the project:

```text
REST API → ADF → ADLS
```

alongside the Day 2 streaming pattern:

```text
Historical public data
        ↓
Simulated event replay
        ↓
Event Hubs
        ↓
ADLS
```

The project explicitly distinguishes between a **real public data source** and a **simulated streaming transport**, maintaining an accurate representation of the architecture.
