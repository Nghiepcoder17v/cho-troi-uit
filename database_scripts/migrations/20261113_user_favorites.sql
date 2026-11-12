-- Chợ Trời UIT: private saved-product relation (DB-6A).
-- Additive SQL Server migration. Verify backup/recovery before applying to a database with data.
-- Never run database_scripts/01_init_schema.sql against an existing database.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.USERS', N'U') IS NULL
    THROW 51020, 'dbo.USERS does not exist; apply the base schema first.', 1;
IF OBJECT_ID(N'dbo.PRODUCTS', N'U') IS NULL
    THROW 51021, 'dbo.PRODUCTS does not exist; apply the base schema first.', 1;

BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.USER_FAVORITES', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.USER_FAVORITES (
        user_id INT NOT NULL,
        product_id INT NOT NULL,
        created_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_UserFavorites_Created DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_UserFavorites PRIMARY KEY CLUSTERED (user_id ASC, product_id ASC),
        CONSTRAINT FK_UserFavorites_User FOREIGN KEY (user_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_UserFavorites_Product FOREIGN KEY (product_id)
            REFERENCES dbo.PRODUCTS (product_id)
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.USER_FAVORITES')
      AND name = N'IX_UserFavorites_UserCreated'
)
BEGIN
    CREATE INDEX IX_UserFavorites_UserCreated
        ON dbo.USER_FAVORITES (user_id ASC, created_at DESC, product_id DESC);
END;

COMMIT TRANSACTION;
