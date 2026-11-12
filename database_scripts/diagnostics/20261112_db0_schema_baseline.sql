/*
    Chợ Trời UIT — DB-0 read-only schema diagnostic
    Date: 2026-11-12

    SAFETY:
    - This script is read-only. It queries SQL Server catalog metadata only.
    - It does not read application rows, create objects, change data, or run migrations.
    - It intentionally requires a dedicated database whose name ends with "_test".
    - Connect SSMS to the intended test database before executing.
*/
SET NOCOUNT ON;

IF RIGHT(LOWER(DB_NAME()), 5) <> N'_test'
BEGIN
    ;THROW 52000, 'Safety stop: connect to a dedicated SQL Server database whose name ends with _test.', 1;
END;

PRINT N'DB-0 schema diagnostic — read-only';
PRINT N'Database: ' + QUOTENAME(DB_NAME());
PRINT N'Server: ' + CONVERT(nvarchar(128), SERVERPROPERTY('ServerName'));
PRINT N'Product version: ' + CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion'));

-- 1. Expected core tables.
DECLARE @ExpectedTables TABLE (
    schema_name sysname NOT NULL,
    table_name sysname NOT NULL
);

INSERT INTO @ExpectedTables (schema_name, table_name)
VALUES
    (N'dbo', N'CATEGORIES'),
    (N'dbo', N'USERS'),
    (N'dbo', N'PRODUCTS'),
    (N'dbo', N'TRANSACTIONS'),
    (N'dbo', N'REVIEWS'),
    (N'dbo', N'MEDIA_ASSETS'),
    (N'dbo', N'PRODUCT_MEDIA'),
    (N'dbo', N'USER_AVATARS'),
    (N'dbo', N'TRANSACTION_EVENTS'),
    (N'dbo', N'TRANSACTION_STATUS_HISTORY');

SELECT
    e.schema_name,
    e.table_name,
    CASE WHEN t.object_id IS NULL THEN N'MISSING' ELSE N'PRESENT' END AS table_status
FROM @ExpectedTables AS e
LEFT JOIN sys.schemas AS s
    ON s.name = e.schema_name
LEFT JOIN sys.tables AS t
    ON t.schema_id = s.schema_id
   AND t.name = e.table_name
ORDER BY e.table_name;

-- 2. Columns and SQL types for core OLTP tables.
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.column_id,
    c.name AS column_name,
    ty.name AS sql_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE s.name = N'dbo'
  AND t.name IN (N'USERS', N'PRODUCTS', N'TRANSACTIONS', N'REVIEWS',
                 N'MEDIA_ASSETS', N'PRODUCT_MEDIA', N'USER_AVATARS',
                 N'TRANSACTION_EVENTS', N'TRANSACTION_STATUS_HISTORY')
ORDER BY t.name, c.column_id;

-- 3. CHECK constraints and their trust/disabled state.
SELECT
    OBJECT_SCHEMA_NAME(cc.parent_object_id) AS schema_name,
    OBJECT_NAME(cc.parent_object_id) AS table_name,
    cc.name AS constraint_name,
    cc.definition,
    cc.is_disabled,
    cc.is_not_trusted
FROM sys.check_constraints AS cc
WHERE cc.parent_object_id IN (
    SELECT t.object_id
    FROM sys.tables AS t
    JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dbo'
      AND t.name IN (N'USERS', N'PRODUCTS', N'TRANSACTIONS', N'REVIEWS',
                     N'MEDIA_ASSETS', N'PRODUCT_MEDIA', N'USER_AVATARS',
                     N'TRANSACTION_EVENTS', N'TRANSACTION_STATUS_HISTORY')
)
ORDER BY table_name, constraint_name;

-- 4. Foreign keys and their trust/disabled state.
SELECT
    OBJECT_SCHEMA_NAME(fk.parent_object_id) AS schema_name,
    OBJECT_NAME(fk.parent_object_id) AS table_name,
    fk.name AS foreign_key_name,
    OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
    fk.is_disabled,
    fk.is_not_trusted
FROM sys.foreign_keys AS fk
WHERE fk.parent_object_id IN (
    SELECT t.object_id
    FROM sys.tables AS t
    JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dbo'
      AND t.name IN (N'USERS', N'PRODUCTS', N'TRANSACTIONS', N'REVIEWS',
                     N'MEDIA_ASSETS', N'PRODUCT_MEDIA', N'USER_AVATARS',
                     N'TRANSACTION_EVENTS', N'TRANSACTION_STATUS_HISTORY')
)
ORDER BY table_name, foreign_key_name;

-- 5. Indexes, including filtered-index definitions.
SELECT
    OBJECT_SCHEMA_NAME(i.object_id) AS schema_name,
    OBJECT_NAME(i.object_id) AS table_name,
    i.name AS index_name,
    i.type_desc,
    i.is_unique,
    i.is_primary_key,
    i.is_unique_constraint,
    i.has_filter,
    i.filter_definition,
    i.is_disabled
FROM sys.indexes AS i
WHERE i.object_id IN (
    SELECT t.object_id
    FROM sys.tables AS t
    JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dbo'
      AND t.name IN (N'USERS', N'PRODUCTS', N'TRANSACTIONS', N'REVIEWS',
                     N'MEDIA_ASSETS', N'PRODUCT_MEDIA', N'USER_AVATARS',
                     N'TRANSACTION_EVENTS', N'TRANSACTION_STATUS_HISTORY')
)
  AND i.index_id > 0
ORDER BY table_name, index_name;

-- 6. Triggers attached to core OLTP tables.
SELECT
    OBJECT_SCHEMA_NAME(tr.parent_id) AS schema_name,
    OBJECT_NAME(tr.parent_id) AS table_name,
    tr.name AS trigger_name,
    tr.is_disabled,
    tr.is_instead_of_trigger
FROM sys.triggers AS tr
WHERE tr.parent_class = 1
  AND tr.parent_id IN (
      SELECT t.object_id
      FROM sys.tables AS t
      JOIN sys.schemas AS s ON s.schema_id = t.schema_id
      WHERE s.name = N'dbo'
        AND t.name IN (N'USERS', N'PRODUCTS', N'TRANSACTIONS')
  )
ORDER BY table_name, trigger_name;

-- 7. Feature markers. These report schema presence only, not migration history.
SELECT
    DB_NAME() AS database_name,
    CASE WHEN COL_LENGTH(N'dbo.USERS', N'bio') IS NULL THEN 0 ELSE 1 END AS has_user_bio,
    CASE WHEN COL_LENGTH(N'dbo.USERS', N'student_id') = 8 THEN 1 ELSE 0 END AS student_id_is_8_bytes,
    CASE WHEN COL_LENGTH(N'dbo.TRANSACTIONS', N'buyer_confirmed_at') IS NULL THEN 0 ELSE 1 END AS has_buyer_confirmed_at,
    CASE WHEN COL_LENGTH(N'dbo.TRANSACTIONS', N'seller_confirmed_at') IS NULL THEN 0 ELSE 1 END AS has_seller_confirmed_at,
    CASE WHEN OBJECT_ID(N'dbo.REVIEWS', N'U') IS NULL THEN 0 ELSE 1 END AS has_reviews,
    CASE WHEN OBJECT_ID(N'dbo.MEDIA_ASSETS', N'U') IS NULL THEN 0 ELSE 1 END AS has_media_assets,
    CASE WHEN OBJECT_ID(N'dbo.PRODUCT_MEDIA', N'U') IS NULL THEN 0 ELSE 1 END AS has_product_media,
    CASE WHEN OBJECT_ID(N'dbo.USER_AVATARS', N'U') IS NULL THEN 0 ELSE 1 END AS has_user_avatars,
    CASE
        WHEN OBJECT_ID(N'dbo.TRANSACTION_EVENTS', N'U') IS NOT NULL
          OR OBJECT_ID(N'dbo.TRANSACTION_STATUS_HISTORY', N'U') IS NOT NULL
        THEN 1 ELSE 0
    END AS has_transaction_event_history;

PRINT N'Diagnostic completed. No application rows were selected and no schema/data was modified.';
