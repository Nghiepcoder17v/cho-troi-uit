-- Chuẩn hóa MSSV: đúng 8 chữ số theo quy tắc tài khoản UIT.
-- Sao lưu database và xử lý dữ liệu không hợp lệ trước khi áp dụng.
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.USERS', N'U') IS NULL
    THROW 51000, 'dbo.USERS does not exist; apply the base schema first.', 1;

IF EXISTS (
    SELECT 1
    FROM dbo.USERS
    WHERE LEN(student_id) <> 8
       OR student_id LIKE '%[^0-9]%'
)
    THROW 51001, 'USERS contains student_id values that are not exactly 8 digits. Correct them before migrating.', 1;

BEGIN TRANSACTION;

IF COL_LENGTH(N'dbo.USERS', N'student_id') <> 8
BEGIN
    -- SQL Server will not alter a column while its UNIQUE constraint exists.
    IF EXISTS (
        SELECT 1
        FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID(N'dbo.USERS')
          AND name = N'UQ_Users_StudentId'
    )
        ALTER TABLE dbo.USERS DROP CONSTRAINT UQ_Users_StudentId;

    ALTER TABLE dbo.USERS ALTER COLUMN student_id VARCHAR(8) NOT NULL;
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.USERS')
      AND name = N'UQ_Users_StudentId'
)
    ALTER TABLE dbo.USERS ADD CONSTRAINT UQ_Users_StudentId UNIQUE (student_id);

IF OBJECT_ID(N'dbo.CK_Users_StudentIdFormat', N'C') IS NULL
BEGIN
    ALTER TABLE dbo.USERS WITH CHECK
        ADD CONSTRAINT CK_Users_StudentIdFormat
        CHECK (LEN(student_id) = 8 AND student_id NOT LIKE '%[^0-9]%');
END;
ELSE
    ALTER TABLE dbo.USERS WITH CHECK CHECK CONSTRAINT CK_Users_StudentIdFormat;

COMMIT TRANSACTION;
