-- Chợ Trời UIT: product-report intake (DB-6B).
-- Additive SQL Server migration. No existing application data is dropped or rewritten.
-- Preserve report history: both foreign keys intentionally use NO ACTION (no cascade).
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.USERS', N'U') IS NULL
    THROW 51030, 'dbo.USERS does not exist; apply the base schema first.', 1;
IF OBJECT_ID(N'dbo.PRODUCTS', N'U') IS NULL
    THROW 51031, 'dbo.PRODUCTS does not exist; apply the base schema first.', 1;

BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.PRODUCT_REPORTS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PRODUCT_REPORTS (
        report_id BIGINT IDENTITY(1,1) NOT NULL,
        reporter_user_id INT NOT NULL,
        target_product_id INT NOT NULL,
        reason_code VARCHAR(32) NOT NULL,
        description NVARCHAR(500) NULL,
        status VARCHAR(16) NOT NULL
            CONSTRAINT DF_ProductReports_Status DEFAULT 'Submitted',
        submitted_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_ProductReports_Submitted DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_ProductReports_Updated DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_ProductReports PRIMARY KEY CLUSTERED (report_id),
        CONSTRAINT FK_ProductReports_Reporter FOREIGN KEY (reporter_user_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_ProductReports_Product FOREIGN KEY (target_product_id)
            REFERENCES dbo.PRODUCTS (product_id),
        CONSTRAINT CHK_ProductReports_ReasonCode CHECK (
            reason_code IN (
                'PROHIBITED_ITEM',
                'MISLEADING_LISTING',
                'SUSPECTED_SCAM',
                'SPAM_OR_DUPLICATE',
                'OTHER'
            )
        ),
        CONSTRAINT CHK_ProductReports_Description CHECK (
            description IS NULL OR LEN(description) <= 500
        ),
        CONSTRAINT CHK_ProductReports_Status CHECK (status IN ('Submitted'))
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'IX_ProductReports_ReporterSubmitted'
)
BEGIN
    CREATE INDEX IX_ProductReports_ReporterSubmitted
        ON dbo.PRODUCT_REPORTS
            (reporter_user_id ASC, submitted_at DESC, report_id DESC);
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'IX_ProductReports_StatusSubmitted'
)
BEGIN
    CREATE INDEX IX_ProductReports_StatusSubmitted
        ON dbo.PRODUCT_REPORTS
            (status ASC, submitted_at ASC, report_id ASC);
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.PRODUCT_REPORTS')
      AND name = N'UX_ProductReports_ReporterTargetOpen'
)
BEGIN
    CREATE UNIQUE INDEX UX_ProductReports_ReporterTargetOpen
        ON dbo.PRODUCT_REPORTS (reporter_user_id ASC, target_product_id ASC)
        WHERE status = 'Submitted';
END;

COMMIT TRANSACTION;
