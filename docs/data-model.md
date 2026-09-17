# Data Model

## 1. Modeling Approach

The project uses a fact constellation (galaxy) model rather
than forcing all analytical domains into a single star schema.

## 2. Fact tables

### FACT_PUBLIC_HEALTH

Grain:
One public-health surveillance observation.

Key analytical attributes:

- date/month
- geography
- reported case measure

### FACT_ADVERSE_EVENTS

Grain:
One adverse-event report/observation at the selected
analytical grain.

The source may contain multiple drugs and reactions within
one report.

## Dimensions

### DIM_DATE

Common date/time attributes.

### DIM_REGION

Geographic attributes such as:

- state
- state FIPS
- county
- county FIPS

### DIM_DRUG

Standardized drug attributes used by the adverse-event
analysis.

## 3. Why two fact tables?

Public-health surveillance and drug adverse-event reports
represent different business processes and grains.

There is no reliable event-level key that should be used
to directly join these two fact tables.

Shared dimensions are used where they are semantically
valid.
