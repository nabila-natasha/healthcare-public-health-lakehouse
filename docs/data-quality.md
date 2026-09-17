# Data Quality

## Quality objectives

The pipeline validates data before analytical consumption.

## Bronze validation

Checks include:

- required fields present
- expected data types
- valid ingestion timestamp
- source record structure
- malformed records routed to quarantine

## Silver validation

Checks include:

- valid dates
- valid geographic codes
- non-negative case measures
- standardized categorical values
- duplicate detection
- null-rate monitoring

## Gold validation

Checks include:

- fact-table grain validation
- referential integrity
- aggregation reconciliation
- expected date coverage
- anomaly/outlier review

## Quarantine

Records failing structural or business validation are
stored separately rather than silently discarded.

## Testing

Automated tests will use small local fixtures rather than
live Azure resources or external APIs.
