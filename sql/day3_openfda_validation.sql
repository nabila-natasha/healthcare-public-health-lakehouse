-- Day 3: openFDA Bronze Validation
-- Synapse Serverless SQL
--
-- Purpose:
-- Validate that the openFDA Bronze dataset is queryable,
-- contains the expected records, and preserves the report-level grain.

-- ============================================================
-- 1. Sample Bronze records
-- ============================================================

SELECT TOP 10 *
FROM OPENROWSET(
    BULK 'https://stlakehousebello.dfs.core.windows.net/healthcare/bronze/openfda/openfda_adverse_events.csv',
    FORMAT = 'CSV',
    PARSER_VERSION = '2.0',
    HEADER_ROW = TRUE
) AS rows;


-- ============================================================
-- 2. Row-count and uniqueness validation
-- Expected:
--   bronze_row_count = 100
--   distinct_report_count = 100
-- ============================================================

SELECT
    COUNT(*) AS bronze_row_count,
    COUNT(DISTINCT safetyreportid) AS distinct_report_count,
    COUNT(*) - COUNT(DISTINCT safetyreportid) AS duplicate_report_count
FROM OPENROWSET(
    BULK 'https://stlakehousebello.dfs.core.windows.net/healthcare/bronze/openfda/openfda_adverse_events.csv',
    FORMAT = 'CSV',
    PARSER_VERSION = '2.0',
    HEADER_ROW = TRUE
) AS rows;


-- ============================================================
-- 3. Serious-event distribution
-- ============================================================

SELECT
    serious,
    COUNT(*) AS report_count
FROM OPENROWSET(
    BULK 'https://stlakehousebello.dfs.core.windows.net/healthcare/bronze/openfda/openfda_adverse_events.csv',
    FORMAT = 'CSV',
    PARSER_VERSION = '2.0',
    HEADER_ROW = TRUE
) AS rows
GROUP BY serious
ORDER BY report_count DESC;


-- ============================================================
-- 4. Reporter-country distribution
-- ============================================================

SELECT
    reportercountry,
    COUNT(*) AS report_count
FROM OPENROWSET(
    BULK 'https://stlakehousebello.dfs.core.windows.net/healthcare/bronze/openfda/openfda_adverse_events.csv',
    FORMAT = 'CSV',
    PARSER_VERSION = '2.0',
    HEADER_ROW = TRUE
) AS rows
GROUP BY reportercountry
ORDER BY report_count DESC;


-- ============================================================
-- 5. Required-field validation
-- ============================================================

SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN safetyreportid IS NULL THEN 1 ELSE 0 END)
        AS missing_safetyreportid,
    SUM(CASE WHEN transmissiondate IS NULL THEN 1 ELSE 0 END)
        AS missing_transmissiondate,
    SUM(CASE WHEN receivedate IS NULL THEN 1 ELSE 0 END)
        AS missing_receivedate,
    SUM(CASE WHEN receiptdate IS NULL THEN 1 ELSE 0 END)
        AS missing_receiptdate
FROM OPENROWSET(
    BULK 'https://stlakehousebello.dfs.core.windows.net/healthcare/bronze/openfda/openfda_adverse_events.csv',
    FORMAT = 'CSV',
    PARSER_VERSION = '2.0',
    HEADER_ROW = TRUE
) AS rows;
