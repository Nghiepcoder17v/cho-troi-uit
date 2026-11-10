-- Chợ Trời UIT: hệ thống đánh giá hai chiều cho giao dịch Completed.
-- Migration cộng thêm cho database hiện hữu. Backup DB trước khi chạy.
-- Không chạy 01_init_schema.sql trên database đang có dữ liệu.
SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;

IF OBJECT_ID('dbo.REVIEWS', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.REVIEWS (
        review_id      INT IDENTITY (1, 1) NOT NULL,
        transaction_id INT NOT NULL,
        reviewer_id    INT NOT NULL,
        reviewee_id    INT NOT NULL,
        rating         INT NOT NULL,
        comment        NVARCHAR(1000) NULL,
        created_at     DATETIME2(0) NOT NULL
            CONSTRAINT DF_Reviews_Created DEFAULT SYSUTCDATETIME(),
        updated_at     DATETIME2(0) NOT NULL
            CONSTRAINT DF_Reviews_Updated DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_Reviews PRIMARY KEY (review_id),
        CONSTRAINT FK_Reviews_Transaction FOREIGN KEY (transaction_id)
            REFERENCES dbo.TRANSACTIONS (transaction_id),
        CONSTRAINT FK_Reviews_Reviewer FOREIGN KEY (reviewer_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT FK_Reviews_Reviewee FOREIGN KEY (reviewee_id)
            REFERENCES dbo.USERS (user_id),
        CONSTRAINT UQ_Reviews_Transaction_Reviewer
            UNIQUE (transaction_id, reviewer_id),
        CONSTRAINT CHK_Review_Rating CHECK (rating BETWEEN 1 AND 5),
        CONSTRAINT CHK_Review_Comment CHECK (comment IS NULL OR LEN(comment) <= 1000)
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.REVIEWS')
      AND name = 'IX_Reviews_Reviewee_Created'
)
    CREATE INDEX IX_Reviews_Reviewee_Created
        ON dbo.REVIEWS (reviewee_id, created_at DESC);

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.REVIEWS')
      AND name = 'IX_Reviews_Transaction'
)
    CREATE INDEX IX_Reviews_Transaction
        ON dbo.REVIEWS (transaction_id);

COMMIT TRANSACTION;
