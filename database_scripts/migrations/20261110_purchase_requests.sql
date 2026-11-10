-- Chợ Trời UIT: mua bằng yêu cầu và xác nhận hoàn tất từ hai bên.
-- Migration cộng thêm cho database hiện hữu. Backup DB trước khi chạy.
-- KHÔNG chạy database_scripts/01_init_schema.sql trên dữ liệu đang dùng vì file đó DROP các bảng.
SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;

IF COL_LENGTH('dbo.TRANSACTIONS', 'buyer_confirmed_at') IS NULL
BEGIN
    ALTER TABLE dbo.TRANSACTIONS ADD buyer_confirmed_at DATETIME2(0) NULL;
END;

IF COL_LENGTH('dbo.TRANSACTIONS', 'seller_confirmed_at') IS NULL
BEGIN
    ALTER TABLE dbo.TRANSACTIONS ADD seller_confirmed_at DATETIME2(0) NULL;
END;

IF OBJECT_ID('dbo.CHK_Product_Status', 'C') IS NOT NULL
BEGIN
    ALTER TABLE dbo.PRODUCTS DROP CONSTRAINT CHK_Product_Status;
END;

ALTER TABLE dbo.PRODUCTS WITH CHECK
ADD CONSTRAINT CHK_Product_Status
CHECK (status IN ('Available', 'Reserved', 'Sold', 'Hidden'));

IF OBJECT_ID('dbo.CHK_Transaction_Status', 'C') IS NOT NULL
BEGIN
    ALTER TABLE dbo.TRANSACTIONS DROP CONSTRAINT CHK_Transaction_Status;
END;

ALTER TABLE dbo.TRANSACTIONS WITH CHECK
ADD CONSTRAINT CHK_Transaction_Status
CHECK (status IN ('Pending', 'Accepted', 'Completed', 'Cancelled'));

-- Giữ nguyên UX_Transactions_ActiveProduct: giao dịch Cancelled không còn khóa sản phẩm.
-- Completed rows cũ giữ nguyên; timestamp xác nhận lịch sử để NULL, không giả lập dữ liệu.
COMMIT TRANSACTION;
