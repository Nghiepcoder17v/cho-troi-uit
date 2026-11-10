-- ==============================================================================
-- PROJECT : Chợ Trời UIT (UIT Exchange)
-- SCRIPT  : 01_init_schema.sql
-- TARGET  : SQL Server 2016+ (dùng DROP ... IF EXISTS)
-- NOTE    : Script này XOÁ và TẠO LẠI toàn bộ bảng -> chỉ dùng cho môi trường dev.
--           Chạy trên database đã tạo sẵn, ví dụ:  CREATE DATABASE ChoTroUIT;
-- QUY ƯỚC : - Thời gian lưu theo UTC (SYSUTCDATETIME), khớp với backend (models.py)
--           - Mọi bảng có updated_at để Incremental ETL bắt được cả thay đổi (vd: Available -> Sold)
-- ==============================================================================
SET NOCOUNT ON;
GO

DROP TABLE IF EXISTS TRANSACTIONS;
DROP TABLE IF EXISTS PRODUCTS;
DROP TABLE IF EXISTS USERS;
DROP TABLE IF EXISTS CATEGORIES;
GO

-- 1. DANH MỤC SẢN PHẨM
CREATE TABLE CATEGORIES (
    category_id   INT IDENTITY (1, 1) NOT NULL,
    category_name NVARCHAR(50) NOT NULL,

    CONSTRAINT PK_Categories PRIMARY KEY (category_id),
    CONSTRAINT UQ_Categories_Name UNIQUE (category_name)
);
GO

-- 2. NGƯỜI DÙNG (chỉ nhận sinh viên UIT)
CREATE TABLE USERS (
    user_id       INT IDENTITY (1, 1) NOT NULL,
    student_id    VARCHAR(10)   NOT NULL,
    email         VARCHAR(100)  NOT NULL,
    password_hash VARCHAR(100)  NOT NULL,   -- bcrypt (60 ký tự), KHÔNG lưu mật khẩu thô
    full_name     NVARCHAR(100) NOT NULL,
    major         NVARCHAR(50)  NULL,
    created_at    DATETIME2(0)  NOT NULL CONSTRAINT DF_Users_Created DEFAULT SYSUTCDATETIME(),
    updated_at    DATETIME2(0)  NOT NULL CONSTRAINT DF_Users_Updated DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Users PRIMARY KEY (user_id),
    CONSTRAINT UQ_Users_StudentId UNIQUE (student_id),
    CONSTRAINT UQ_Users_Email UNIQUE (email),
    -- Chỉ nhận đúng đuôi email trường (neo cuối chuỗi, không cho "...uit.edu.vn.evil.com")
    CONSTRAINT CHK_User_Email CHECK (email LIKE '%@gm.uit.edu.vn')
);
GO

-- 3. SẢN PHẨM
CREATE TABLE PRODUCTS (
    product_id  INT IDENTITY (1, 1) NOT NULL,
    seller_id   INT            NOT NULL,
    category_id INT            NOT NULL,
    title       NVARCHAR(200)  NOT NULL,
    description NVARCHAR(MAX)  NULL,
    price       DECIMAL(10, 2) NOT NULL,
    condition   VARCHAR(20)    NOT NULL,
    status      VARCHAR(20)    NOT NULL CONSTRAINT DF_Products_Status DEFAULT 'Available',
    created_at  DATETIME2(0)   NOT NULL CONSTRAINT DF_Products_Created DEFAULT SYSUTCDATETIME(),
    updated_at  DATETIME2(0)   NOT NULL CONSTRAINT DF_Products_Updated DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Products PRIMARY KEY (product_id),
    CONSTRAINT FK_Products_Seller   FOREIGN KEY (seller_id)   REFERENCES USERS (user_id),
    CONSTRAINT FK_Products_Category FOREIGN KEY (category_id) REFERENCES CATEGORIES (category_id),
    CONSTRAINT CHK_Product_Price     CHECK (price >= 0),
    CONSTRAINT CHK_Product_Condition CHECK (condition IN ('Brand New', 'Like New', 'Good', 'Fair')),
    CONSTRAINT CHK_Product_Status    CHECK (status IN ('Available', 'Reserved', 'Sold', 'Hidden'))
);
GO

-- 4. GIAO DỊCH (bảng Fact cho Data Pipeline)
CREATE TABLE TRANSACTIONS (
    transaction_id   INT IDENTITY (1, 1) NOT NULL,
    product_id       INT            NOT NULL,
    buyer_id         INT            NOT NULL,
    amount           DECIMAL(10, 2) NOT NULL,   -- giá chốt cuối (có thể thấp hơn giá niêm yết)
    status           VARCHAR(20)    NOT NULL CONSTRAINT DF_Transactions_Status DEFAULT 'Pending',
    transaction_date DATETIME2(0)   NOT NULL CONSTRAINT DF_Transactions_Date DEFAULT SYSUTCDATETIME(),
    updated_at       DATETIME2(0)   NOT NULL CONSTRAINT DF_Transactions_Updated DEFAULT SYSUTCDATETIME(),
    buyer_confirmed_at DATETIME2(0) NULL,
    seller_confirmed_at DATETIME2(0) NULL,

    CONSTRAINT PK_Transactions PRIMARY KEY (transaction_id),
    CONSTRAINT FK_Transactions_Product FOREIGN KEY (product_id) REFERENCES PRODUCTS (product_id),
    CONSTRAINT FK_Transactions_Buyer   FOREIGN KEY (buyer_id)   REFERENCES USERS (user_id),
    CONSTRAINT CHK_Transaction_Amount CHECK (amount >= 0),
    CONSTRAINT CHK_Transaction_Status CHECK (status IN ('Pending', 'Accepted', 'Completed', 'Cancelled'))
);
GO

-- ==============================================================================
-- INDEX
-- ==============================================================================
-- Mỗi sản phẩm chỉ có TỐI ĐA 1 giao dịch chưa hủy (Pending/Accepted/Completed).
-- Đây là lớp chặn cuối cùng cho race condition: 2 người mua cùng lúc -> 1 người bị lỗi unique.
CREATE UNIQUE INDEX UX_Transactions_ActiveProduct
    ON TRANSACTIONS (product_id) WHERE status <> 'Cancelled';

-- Phục vụ API (lọc theo danh mục + trạng thái, sắp xếp mới nhất)
CREATE INDEX IX_Products_Category_Status_Created ON PRODUCTS (category_id, status, created_at DESC);
CREATE INDEX IX_Products_Seller ON PRODUCTS (seller_id);
-- Lưu ý: tìm kiếm "%từ khoá%" (LIKE có % ở đầu) KHÔNG tận dụng được index này;
-- nó chỉ giúp khi tìm theo tiền tố hoặc ORDER BY title.
CREATE INDEX IX_Products_Title ON PRODUCTS (title);
CREATE INDEX IX_Transactions_Buyer ON TRANSACTIONS (buyer_id);
CREATE INDEX IX_Transactions_Date ON TRANSACTIONS (transaction_date);

-- 5. ĐÁNH GIÁ HAI CHIỀU SAU GIAO DỊCH
CREATE TABLE REVIEWS (
    review_id      INT IDENTITY (1, 1) NOT NULL,
    transaction_id INT NOT NULL,
    reviewer_id    INT NOT NULL,
    reviewee_id    INT NOT NULL,
    rating         INT NOT NULL,
    comment        NVARCHAR(1000) NULL,
    created_at     DATETIME2(0) NOT NULL CONSTRAINT DF_Reviews_Created DEFAULT SYSUTCDATETIME(),
    updated_at     DATETIME2(0) NOT NULL CONSTRAINT DF_Reviews_Updated DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Reviews PRIMARY KEY (review_id),
    CONSTRAINT FK_Reviews_Transaction FOREIGN KEY (transaction_id) REFERENCES TRANSACTIONS (transaction_id),
    CONSTRAINT FK_Reviews_Reviewer FOREIGN KEY (reviewer_id) REFERENCES USERS (user_id),
    CONSTRAINT FK_Reviews_Reviewee FOREIGN KEY (reviewee_id) REFERENCES USERS (user_id),
    CONSTRAINT UQ_Reviews_Transaction_Reviewer UNIQUE (transaction_id, reviewer_id),
    CONSTRAINT CHK_Review_Rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT CHK_Review_Comment CHECK (comment IS NULL OR LEN(comment) <= 1000)
);
GO

CREATE INDEX IX_Reviews_Reviewee_Created ON REVIEWS (reviewee_id, created_at DESC);
CREATE INDEX IX_Reviews_Transaction ON REVIEWS (transaction_id);
GO

-- Phục vụ Incremental ETL: WHERE updated_at > @last_watermark
CREATE INDEX IX_Users_UpdatedAt ON USERS (updated_at);
CREATE INDEX IX_Products_UpdatedAt ON PRODUCTS (updated_at);
CREATE INDEX IX_Transactions_UpdatedAt ON TRANSACTIONS (updated_at);
GO

-- ==============================================================================
-- TRIGGER: tự cập nhật updated_at khi có UPDATE mà không set updated_at
-- (backend đã tự set; trigger là lưới an toàn cho câu UPDATE chạy tay trong SSMS)
-- ==============================================================================
CREATE TRIGGER TRG_Users_UpdatedAt ON USERS AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(updated_at) RETURN;
    UPDATE t SET updated_at = SYSUTCDATETIME()
    FROM USERS AS t INNER JOIN inserted AS i ON t.user_id = i.user_id;
END;
GO

CREATE TRIGGER TRG_Products_UpdatedAt ON PRODUCTS AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(updated_at) RETURN;
    UPDATE t SET updated_at = SYSUTCDATETIME()
    FROM PRODUCTS AS t INNER JOIN inserted AS i ON t.product_id = i.product_id;
END;
GO

CREATE TRIGGER TRG_Transactions_UpdatedAt ON TRANSACTIONS AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(updated_at) RETURN;
    UPDATE t SET updated_at = SYSUTCDATETIME()
    FROM TRANSACTIONS AS t INNER JOIN inserted AS i ON t.transaction_id = i.transaction_id;
END;
GO
