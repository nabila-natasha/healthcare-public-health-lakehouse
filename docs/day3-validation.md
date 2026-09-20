# Day 3 Validation — openFDA Batch Ingestion

## Objective

Validate the end-to-end openFDA batch ingestion path:

```text
openFDA
   ↓
ADF REST/HTTP
   ↓
ADLS RAW
   ↓
Bronze
   ↓
Synapse validation
```

---

# 1. Pre-Execution Checks

## Git

```text
[x] Day 3 feature branch created
```

Expected branch:

```text
feature/day3-openfda-batch
```

---

## Azure resources

```text
[x] Resource group exists
[x] ADLS Gen2 exists
[x] healthcare filesystem exists
[x] ADF exists
[x] Synapse exists
```

---

# 2. ADF Configuration

## REST linked service

Name:

```text
LS_openFDA_REST
```

Validation:

```text
[x] Created
[x] Connection test successful
```

---

## ADLS linked service

Name:

```text
LS_ADLS_healthcare
```

Authentication:

```text
Managed Identity
```

Validation:

```text
[x] Created
[x] Connection test successful
```

---

## REST dataset

Name:

```text
DS_openFDA_REST
```

Validation:

```text
[x] Created
[x] API endpoint configured
[x] Sample response verified
```

Endpoint used by the pipeline:

```text
drug/event.json?limit=100
```

The request retrieves a bounded response containing 100 adverse-event records.

---

## RAW dataset

Name:

```text
DS_openFDA_RAW
```

Validation:

```text
[x] Created
[x] ADLS filesystem configured
[x] openFDA RAW path configured
```

Configured destination:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

---

# 3. Pipeline

Name:

```text
PL_openFDA_Batch_Ingestion
```

Expected flow:

```text
REST source
     ↓
Copy Activity
     ↓
ADLS RAW
```

Validation:

```text
[x] Pipeline created
[x] Source configured
[x] Sink configured
[x] Debug run successful
```

Copy Activity:

```text
Copy_openFDA_to_RAW
```

---

# 4. Execution Evidence

## ADF Monitor

Status:

```text
Succeeded
```

Execution date:

```text
2026-09-20
```

Copy Activity:

```text
Copy_openFDA_to_RAW
```

ADF integration runtime:

```text
AutoResolveIntegrationRuntime (Southeast Asia)
```

Copy duration:

```text
21 seconds
```

---

# 5. Copy Activity Statistics

Rows read:

```text
1
```

Rows copied:

```text
1
```

Data read:

```text
2,700,352 bytes
```

Data written:

```text
1,599,087 bytes
```

Files written:

```text
1
```

### Interpretation of rows read/copied

The ADF statistics show:

```text
rowsRead   = 1
rowsCopied = 1
```

This does **not** mean that only one adverse-event record was retrieved.

The REST response is one JSON document containing a `results` array. The document contains:

```text
100 adverse-event records
```

Therefore:

```text
ADF rows read/copied = 1 JSON document
openFDA records      = 100 records
```

---

# 6. ADLS Validation

Expected location:

```text
healthcare/raw/openfda/
```

Validation:

```text
[x] Directory exists
[x] Output file exists
[x] File is non-empty
[x] Source records present
```

Actual path:

```text
healthcare/raw/openfda/openfda_adverse_events.json
```

RAW file size:

```text
1,599,087 bytes
```

---

# 7. Source Data Validation

Validation:

```text
[x] JSON structure inspected
[x] Expected openFDA response structure observed
[x] Sample records inspected
[x] Real public source data confirmed
```

Observed response structure:

```text
{
    "meta": {...},
    "results": [...]
}
```

Source record grain:

```text
One adverse-event report per safetyreportid
```

Source validation performed on the 100 retrieved records:

```text
Input records            : 100
Unique safetyreportid    : 100
Duplicate safetyreportid : 0
```

Required top-level fields:

```text
safetyreportid       : 0 missing
transmissiondate     : 0 missing
receivedate          : 0 missing
receiptdate          : 0 missing
```

One important source-quality observation:

```text
seriousnessdeath     : 96/100 missing
```

These values were preserved as NULL in Bronze rather than converting missing values into zero.

Sample record evidence:

```text
The inspected records contained real FDA adverse-event fields including
safetyreportid, transmissiondate, receivedate, receiptdate, serious,
primarysource, patient, reaction, and drug information.
```

Do not copy unnecessary amounts of source data into Git.

---

# 8. Bronze Validation

The Bronze transformation was executed during development using Python in Azure Cloud Shell.

The transformation:

```text
ADLS RAW JSON
     ↓
Python transformation
     ↓
Bronze CSV
```

Bronze grain:

```text
One row per safetyreportid
```

Bronze validation:

```text
Bronze rows             : 100
Unique safetyreportid   : 100
Duplicate IDs           : 0
Columns                 : 17
```

Bronze file:

```text
healthcare/bronze/openfda/openfda_adverse_events.csv
```

Bronze file size:

```text
1,676,791 bytes
```

The Bronze transformation promotes selected scalar and nested attributes into columns while retaining repeated `reaction` and `drug` arrays as JSON strings.

This avoids multiplying rows through a reaction × drug join at the Bronze layer.

---

# 9. Synapse Validation

Validation:

```text
[x] Synapse can access the Bronze output
[x] Sample records returned
[x] Record count checked
[x] Distinct report count checked
[x] Duplicate report count checked
```

Synapse Serverless validation result:

```text
bronze_row_count       = 100
distinct_report_count  = 100
duplicate_report_count = 0
```

This confirms that the Bronze dataset contains the expected 100 report-level records without duplicate `safetyreportid` values.

Additional validation queries are maintained in:

```text
sql/validation/day3_openfda_validation.sql
```

The validation script contains checks for:

```text
1. Sample Bronze records
2. Row count and uniqueness
3. Serious-event distribution
4. Reporter-country distribution
5. Required-field completeness
```

---

# 10. Security Validation

```text
[x] No storage account key committed
[x] No API secret committed
[x] No connection string committed
[x] ADF uses managed identity for ADLS
[x] Git diff reviewed before commit
```

The openFDA API is publicly accessible and does not require a secret.

ADLS access from ADF uses the ADF managed identity with:

```text
Storage Blob Data Contributor
```

---

# 11. Documentation Evidence

Evidence checklist:

```text
[ ] ADF pipeline screenshot captured
[ ] Successful run screenshot captured
[ ] Activity statistics screenshot captured
[ ] ADLS output screenshot/CLI evidence captured
[ ] Synapse validation evidence captured
```

These should be checked after the screenshots/evidence have been added to the repository or project evidence folder.

---

# 12. Execution Summary

| Validation              |   Expected |          Actual | Result  |
| ----------------------- | ---------: | --------------: | ------- |
| REST source reachable   |        Yes |             Yes | PASS    |
| ADF pipeline created    |        Yes |             Yes | PASS    |
| ADF execution           |  Succeeded |       Succeeded | PASS    |
| RAW output created      |        Yes |             Yes | PASS    |
| RAW file non-empty      |        Yes | 1,599,087 bytes | PASS    |
| Source records present  |        Yes |             100 | PASS    |
| Unique report IDs       |        100 |             100 | PASS    |
| Duplicate report IDs    |          0 |               0 | PASS    |
| Required fields missing |          0 |               0 | PASS    |
| Bronze rows             |        100 |             100 | PASS    |
| Bronze columns          |         17 |              17 | PASS    |
| Synapse validation      | Successful |   100 / 100 / 0 | PASS    |
| Evidence screenshots    |        Yes | Pending capture | PENDING |

---

# 13. Day 3 Technical Status

```text
TECHNICAL PIPELINE STATUS: PASS
REPOSITORY PACKAGING STATUS: IN PROGRESS
```

The technical batch ingestion path has been successfully demonstrated.

The remaining Day 3 work is evidence packaging and Git commit/merge.

---

# 14. Day 3 Gate

Technical requirements:

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

Repository/evidence requirements:

```text
[ ] Evidence screenshots captured
[ ] Documentation updated
[ ] SQL validation script committed
[ ] Changes committed to Git
[ ] Feature branch pushed
[ ] Changes merged to main
```

The Day 3 gate becomes fully complete after the remaining repository and evidence steps are finished.
