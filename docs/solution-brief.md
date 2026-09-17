# Healthcare Public Health Surveillance & Risk Analytics Lakehouse

## 1. Business problem

Public-health organizations need to understand how reported
cases change over time and across geographic regions, while
identifying unusual reporting patterns and supporting
short-term resource planning.

This project demonstrates a cloud lakehouse architecture that
combines historical public-health surveillance data with
drug adverse-event data.

## 2. Business questions

- How are reported cases changing over time and by region?
- Which regions are experiencing the fastest acceleration?
- Where are unusual reporting patterns occurring?
- Which drugs and reactions have the highest reported
  adverse-event volumes?
- Can short-term case volume be forecast for resource planning?

## 3. Data sources

### CDC COVID-19 Case Surveillance

Historical U.S. public-health surveillance records covering
2020-01 through 2024-06.

### openFDA Drug Adverse Events

FDA adverse-event reports accessed through the openFDA API.

## 4. Architecture approach

The solution combines:

- batch API ingestion
- historical event replay
- event streaming
- cloud object storage
- Bronze/Silver/Gold transformation
- serverless SQL analytics
- Power BI
- machine learning

## 5. Streaming approach

The CDC historical records are replayed at an accelerated
cadence through Event Hubs to simulate near-real-time event
arrival.

This is a simulation using historical data and is not a
real-time clinical surveillance system.

## 6. Expected outputs

- curated public-health fact table
- adverse-event fact table
- geographic and date dimensions
- forecasting results
- anomaly results
- Power BI analytical dashboard

## 7. Project limitations

This project uses publicly available historical data.

It does not process PHI, provide clinical decision support,
or represent a production healthcare surveillance platform.
