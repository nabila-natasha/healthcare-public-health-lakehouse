# ADR-001: Use ADLS Gen2 as the Lakehouse Storage Layer

**Status:** Accepted  
**Date:** 2026-09-21  
**Decision owners:** Project implementation team  

---

## Context

The project requires a durable storage layer for a healthcare/public-health lakehouse architecture.

The platform needs to support:

* raw source preservation
* streaming event landing
* Bronze data
* invalid-event quarantine
* downstream analytics
* replay and investigation
* separation of ingestion and transformation layers

The project also needs storage that integrates with the Azure services used elsewhere in the architecture.

---

## Decision

Use **Azure Data Lake Storage Gen2 (ADLS Gen2)** as the primary lakehouse storage layer.

The project uses the following logical zones:

```text
healthcare/
├── raw/
├── bronze/
├── silver/
├── gold/
└── quarantine/
```

The current Azure storage account is:

```text
stlakehousebello
```

with the filesystem:

```text
healthcare
```

---

## Rationale

ADLS Gen2 provides a suitable storage foundation for the project's lakehouse architecture because it supports:

* hierarchical directory organization
* large-scale object storage
* integration with Azure analytics services
* separation of raw and curated data
* file-based replay and investigation
* controlled access through Azure identity and RBAC

The architecture also allows different processing technologies to operate against the same storage layer.

For example:

```text
ADF
  ↓
ADLS RAW

Python/Event Hubs consumer
  ↓
ADLS RAW/Bronze/Quarantine

Synapse
  ↓
ADLS analytical access

Databricks
  ↓
ADLS analytical/ML processing
```

---

## Layer responsibilities

### RAW

Preserves received source data or event messages with minimal transformation.

Examples:

```text
healthcare/raw/openfda/
healthcare/raw/cdc/
```

The Day 4 CDC RAW layer preserves all received Event Hub messages, including messages that later fail validation.

---

### Bronze

Contains data after initial validation and ingestion-level processing.

Examples:

```text
healthcare/bronze/openfda/
healthcare/bronze/cdc/
```

---

### Silver

Reserved for cleaned and conformed analytical data.

Silver is not the primary focus of Day 4.

---

### Gold

Reserved for business-facing analytical datasets and metrics.

---

### Quarantine

Contains invalid or rejected events together with diagnostic information.

Example:

```text
healthcare/quarantine/cdc/
```

This prevents invalid records from silently disappearing.

---

## Security

Access to the storage account is controlled using Azure RBAC and managed identities where supported.

Application secrets and connection strings are kept outside source-controlled code.

The architecture does not rely on publicly accessible blob storage.

---

## Alternatives considered

### Azure Blob Storage

Blob Storage could provide object storage, but ADLS Gen2 provides the hierarchical namespace and lake-oriented organization more appropriate for this project.

### Local filesystem

A local filesystem would not provide a shared cloud storage layer or integration with the Azure analytics architecture.

### Database-first storage

A database-first design would make the raw event/object preservation and replay-oriented architecture less natural.

---

## Consequences

### Positive

* Clear separation between ingestion and analytics layers
* Durable cloud storage
* Suitable integration point for Azure analytics services
* Supports raw-event preservation
* Supports quarantine and replay workflows
* Provides a common storage layer for multiple processing engines

### Trade-offs

* File formats and directory conventions must be governed carefully.
* Small-file generation can become a scalability problem.
* Data lifecycle and retention policies need to be designed for production.
* File-based storage does not by itself provide transactional processing semantics.

---

## Production evolution

A production implementation would additionally consider:

* Parquet as the primary analytical format
* partitioning strategy
* compaction
* lifecycle management
* encryption/key-management requirements
* centralized metadata/catalog services
* data retention policies
* automated storage monitoring
* data access auditing

The current project demonstrates the storage architecture at portfolio scale and does not claim to implement the complete production operating model.

