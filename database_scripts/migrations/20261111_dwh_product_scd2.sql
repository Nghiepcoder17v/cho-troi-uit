-- DWH-only migration: convert dbo.dim_product to SCD Type 2 without deleting rows or facts.
-- Run once against ChoTroUIT_DWH. The ETL metadata.create_all() does not alter existing tables.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.dim_product', N'U') IS NULL
    THROW 50001, 'dbo.dim_product does not exist; initialize the DWH before applying this migration.', 1;

IF COL_LENGTH(N'dbo.dim_product', N'source_updated_at') IS NULL
    ALTER TABLE dbo.dim_product ADD source_updated_at DATETIME2(0) NULL;
IF COL_LENGTH(N'dbo.dim_product', N'effective_from') IS NULL
    ALTER TABLE dbo.dim_product ADD effective_from DATETIME2(0) NULL;
IF COL_LENGTH(N'dbo.dim_product', N'effective_to') IS NULL
    ALTER TABLE dbo.dim_product ADD effective_to DATETIME2(0) NULL;
IF COL_LENGTH(N'dbo.dim_product', N'is_current') IS NULL
    ALTER TABLE dbo.dim_product ADD is_current BIT NULL;

UPDATE dbo.dim_product
SET source_updated_at = COALESCE(source_updated_at, listed_at),
    effective_from = COALESCE(effective_from, listed_at),
    is_current = COALESCE(is_current, 1);

ALTER TABLE dbo.dim_product ALTER COLUMN source_updated_at DATETIME2(0) NOT NULL;
ALTER TABLE dbo.dim_product ALTER COLUMN effective_from DATETIME2(0) NOT NULL;
ALTER TABLE dbo.dim_product ALTER COLUMN is_current BIT NOT NULL;

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE parent_object_id = OBJECT_ID(N'dbo.dim_product')
                 AND name = N'CHK_dim_product_effective_window')
    ALTER TABLE dbo.dim_product ADD CONSTRAINT CHK_dim_product_effective_window
        CHECK (effective_to IS NULL OR effective_to > effective_from);
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE parent_object_id = OBJECT_ID(N'dbo.dim_product')
                 AND name = N'CHK_dim_product_current_window')
    ALTER TABLE dbo.dim_product ADD CONSTRAINT CHK_dim_product_current_window
        CHECK ((is_current = 1 AND effective_to IS NULL)
            OR (is_current = 0 AND effective_to IS NOT NULL));

-- The old schema enforced one row per product_id. Replace that rule with one current row per product.
DECLARE @constraint_name SYSNAME;
SELECT TOP (1) @constraint_name = kc.name
FROM sys.key_constraints AS kc
JOIN sys.index_columns AS ic
  ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
JOIN sys.columns AS c
  ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE kc.parent_object_id = OBJECT_ID(N'dbo.dim_product')
  AND kc.type = 'UQ'
  AND c.name = N'product_id'
  AND ic.key_ordinal = 1
  AND (SELECT COUNT(*) FROM sys.index_columns AS all_ic
       WHERE all_ic.object_id = ic.object_id AND all_ic.index_id = ic.index_id
         AND all_ic.key_ordinal > 0) = 1;
IF @constraint_name IS NOT NULL
    EXEC(N'ALTER TABLE dbo.dim_product DROP CONSTRAINT ' + QUOTENAME(@constraint_name));

DECLARE @index_name SYSNAME;
SELECT TOP (1) @index_name = i.name
FROM sys.indexes AS i
JOIN sys.index_columns AS ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id = OBJECT_ID(N'dbo.dim_product')
  AND i.is_unique = 1 AND i.is_primary_key = 0 AND i.is_unique_constraint = 0
  AND i.name <> N'UX_dim_product_current'
  AND c.name = N'product_id' AND ic.key_ordinal = 1
  AND (SELECT COUNT(*) FROM sys.index_columns AS all_ic
       WHERE all_ic.object_id = ic.object_id AND all_ic.index_id = ic.index_id
         AND all_ic.key_ordinal > 0) = 1;
IF @index_name IS NOT NULL
    EXEC(N'DROP INDEX ' + QUOTENAME(@index_name) + N' ON dbo.dim_product');

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE object_id = OBJECT_ID(N'dbo.dim_product')
                 AND name = N'UX_dim_product_current')
    CREATE UNIQUE INDEX UX_dim_product_current
        ON dbo.dim_product(product_id) WHERE is_current = 1;

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE object_id = OBJECT_ID(N'dbo.dim_product')
                 AND name = N'IX_dim_product_natural_effective')
    CREATE INDEX IX_dim_product_natural_effective
        ON dbo.dim_product(product_id, effective_from);

COMMIT TRANSACTION;
