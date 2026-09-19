/*
===============================================================================
DAY 2 - STREAMING INGESTION VALIDATION
Project: Healthcare Public Health Lakehouse

Purpose:
Validate the Event Hubs -> ADLS Gen2 RAW -> Bronze pipeline using
Synapse Serverless SQL.

Expected test results:
- Event Hubs messages sent: 11
- RAW records: 11
- Unique event IDs in RAW: 10
- Duplicate event: cdc-0005
- Bronze records: 10
- Duplicate Bronze event IDs: 0
===============================================================================
*/


/*
-------------------------------------------------------------------------------
1. TEST A SINGLE RAW JSON FILE
-------------------------------------------------------------------------------
Purpose:
Confirm that Synapse Serverless can read a JSON file from ADLS Gen2.
*/

SELECT
    *
FROM OPENROWSET
(
    BULK 'raw/cdc/ingestion_date=2026-09-19/partition=2/offset=0.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r;


/*
-------------------------------------------------------------------------------
2. COUNT RAW RECORDS
-------------------------------------------------------------------------------
Expected result:
RAW_COUNT = 11

Why 11?
10 source events + 1 intentionally replayed duplicate.
*/

SELECT
    COUNT(*) AS RAW_COUNT
FROM OPENROWSET
(
    BULK 'raw/cdc/ingestion_date=2026-09-19/*/*.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r;


/*
-------------------------------------------------------------------------------
3. EXTRACT RAW EVENT FIELDS
-------------------------------------------------------------------------------
Purpose:
Demonstrate that JSON fields can be queried using normal SQL.
*/

SELECT
    JSON_VALUE(json_content, '$.event.event_id') AS event_id,
    JSON_VALUE(json_content, '$.event.event_time') AS event_time,
    JSON_VALUE(json_content, '$.event.ingestion_time') AS ingestion_time,
    JSON_VALUE(json_content, '$.event.patient_id') AS patient_id,
    JSON_VALUE(json_content, '$.event.event_type') AS event_type,
    JSON_VALUE(json_content, '$.event.region') AS region,
    JSON_VALUE(json_content, '$.event.status') AS status,
    JSON_VALUE(json_content, '$.event_hub_partition')
        AS event_hub_partition,
    JSON_VALUE(json_content, '$.event_hub_offset')
        AS event_hub_offset,
    JSON_VALUE(json_content, '$.received_at')
        AS received_at
FROM OPENROWSET
(
    BULK 'raw/cdc/ingestion_date=2026-09-19/*/*.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r
ORDER BY
    event_id;


/*
-------------------------------------------------------------------------------
4. CHECK FOR DUPLICATE EVENT IDS IN RAW
-------------------------------------------------------------------------------
Expected result:
cdc-0005 appears twice.

This proves that RAW preserves the messages actually received.
*/

SELECT
    JSON_VALUE(json_content, '$.event.event_id') AS event_id,
    COUNT(*) AS received_count
FROM OPENROWSET
(
    BULK 'raw/cdc/ingestion_date=2026-09-19/*/*.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r
GROUP BY
    JSON_VALUE(json_content, '$.event.event_id')
HAVING
    COUNT(*) > 1;


/*
-------------------------------------------------------------------------------
5. COUNT BRONZE RECORDS
-------------------------------------------------------------------------------
Expected result:
BRONZE_COUNT = 10

The duplicate cdc-0005 should not appear in Bronze.
*/

SELECT
    COUNT(*) AS BRONZE_COUNT
FROM OPENROWSET
(
    BULK 'bronze/cdc/ingestion_date=2026-09-19/*.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r;


/*
-------------------------------------------------------------------------------
6. CHECK FOR DUPLICATES IN BRONZE
-------------------------------------------------------------------------------
Expected result:
0 rows.

This confirms that event_id-based deduplication succeeded.
*/

SELECT
    JSON_VALUE(json_content, '$.event_id') AS event_id,
    COUNT(*) AS record_count
FROM OPENROWSET
(
    BULK 'bronze/cdc/ingestion_date=2026-09-19/*.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r
GROUP BY
    JSON_VALUE(json_content, '$.event_id')
HAVING
    COUNT(*) > 1;


/*
-------------------------------------------------------------------------------
7. BRONZE EVENT SUMMARY
-------------------------------------------------------------------------------
Purpose:
Provide a simple analytical validation of the Bronze layer.
*/

SELECT
    JSON_VALUE(json_content, '$.event_type') AS event_type,
    JSON_VALUE(json_content, '$.region') AS region,
    COUNT(*) AS event_count
FROM OPENROWSET
(
    BULK 'bronze/cdc/ingestion_date=2026-09-19/*.json',
    DATA_SOURCE = 'HealthcareLake',
    FORMAT = 'CSV',
    FIELDTERMINATOR = '0x0b',
    FIELDQUOTE = '0x0b',
    ROWTERMINATOR = '0x0b'
)
WITH
(
    json_content VARCHAR(MAX)
) AS r
GROUP BY
    JSON_VALUE(json_content, '$.event_type'),
    JSON_VALUE(json_content, '$.region')
ORDER BY
    event_type,
    region;
