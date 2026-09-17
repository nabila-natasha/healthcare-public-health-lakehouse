# Architecture

## 1. Overview

```text
CDC Historical Public-Health Data
             |
             v
     Python Replay Producer
             |
       Kafka protocol
             |
             v
      Azure Event Hubs
             |
             v
        ADLS Bronze
             |
             v
      Silver -> Gold
             |
       +-----+------+
       |            |
       v            v
Synapse Serverless  Databricks
       |            |
       v            v
   Power BI       ML outputs
                      |
                      v
                  ADLS Gold
                      |
                      v
                  Power BI
```

## 2. Batch Ingestion

```text
openFDA API
    |
    v
Azure Data Factory
    |
    v
ADLS Raw
    |
    v
Bronze
    |
    v
Silver
    |
    v
Gold
```

## 3. Storage Zone

#### RAW
Source data captured with minimal transformation.

#### BRONZE  
Validated source records with ingestion metadata.

#### SILVER  
Cleaned, typed and standardized data.

#### GOLD
Business-ready analytical datasets.



