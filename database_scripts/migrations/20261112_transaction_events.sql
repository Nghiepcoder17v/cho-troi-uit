-- Chợ Trời UIT: append-only transaction event history (DB-4).
-- Additive migration for an existing database. Take and verify a restorable backup first.
-- Do not run database_scripts/01_init_schema.sql against an existing database.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.TRANSACTIONS', N'U') IS NULL
    THROW 51010, 'dbo.TRANSACTIONS does not exist; apply the base schema first.', 1;
IF OBJECT_ID(N'dbo.USERS', N'U') IS NULL
    THROW 51011, 'dbo.USERS does not exist; apply the base schema first.', 1;

BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.TRANSACTION_EVENTS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TRANSACTION_EVENTS (
        event_id BIGINT IDENTITY(1, 1) NOT NULL,
        transaction_id INT NOT NULL,
        actor_user_id INT NULL,
        event_type VARCHAR(32) NOT NULL,
        from_status VARCHAR(20) NULL,
        to_status VARCHAR(20) NOT NULL,
        occurred_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_TransactionEvents_Occurred DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_TransactionEvents PRIMARY KEY (event_id),
        CONSTRAINT FK_TransactionEvents_Transaction FOREIGN KEY (transaction_id)
            REFERENCES dbo.TRANSACTIONS (transaction_id),
        CONSTRAINT FK_TransactionEvents_Actor FOREIGN KEY (actor_user_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT CHK_TransactionEvents_EventType CHECK (
            event_type IN (
                'REQUEST_CREATED',
                'SELLER_ACCEPTED',
                'SELLER_REJECTED',
                'BUYER_CANCELLED',
                'SELLER_CANCELLED',
                'BUYER_CONFIRMED',
                'SELLER_CONFIRMED',
                'TRANSACTION_COMPLETED'
            )
        ),
        CONSTRAINT CHK_TransactionEvents_FromStatus CHECK (
            from_status IS NULL OR from_status IN ('Pending', 'Accepted', 'Completed', 'Cancelled')
        ),
        CONSTRAINT CHK_TransactionEvents_ToStatus CHECK (
            to_status IN ('Pending', 'Accepted', 'Completed', 'Cancelled')
        )
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.TRANSACTION_EVENTS')
      AND name = N'IX_TransactionEvents_TransactionOccurred'
)
BEGIN
    CREATE INDEX IX_TransactionEvents_TransactionOccurred
        ON dbo.TRANSACTION_EVENTS (transaction_id, occurred_at, event_id);
END;

COMMIT TRANSACTION;
