-- ==============================================================================
-- SCRIPT : 02_seed_reference_data.sql
-- MỤC ĐÍCH: Dữ liệu danh mục bắt buộc để API đăng bán hoạt động (chạy sau 01).
--           Idempotent: chạy nhiều lần không bị trùng.
-- ==============================================================================
SET NOCOUNT ON;
GO

IF NOT EXISTS (SELECT 1 FROM CATEGORIES)
BEGIN
    INSERT INTO CATEGORIES (category_name) VALUES
        (N'Giáo trình'),
        (N'Linh kiện IT'),
        (N'Bàn phím & Chuột'),
        (N'Phương tiện'),
        (N'Khác');
END;
GO
