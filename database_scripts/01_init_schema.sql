-- ==============================================================================
-- PROJECT: Chợ Trời UIT (UIT Exchange)
-- SCRIPT: 01_init_schema.sql
-- DESCRIPTION: Khởi tạo các bảng cốt lõi (OLTP) chuẩn 3NF
-- ==============================================================================

-- 1. BẢNG DANH MỤC SẢN PHẨM
CREATE TABLE CATEGORIES (
    category_id INT IDENTITY (1, 1) PRIMARY KEY,
    category_name NVARCHAR(50) UNIQUE NOT NULL
);

-- 2. BẢNG NGƯỜI DÙNG (Chỉ nhận sinh viên UIT)
CREATE TABLE USERS (
    user_id INT IDENTITY (1, 1) PRIMARY KEY,
    student_id VARCHAR(10) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    full_name NVARCHAR(100) NOT NULL,
    major NVARCHAR(50),
    created_at DATETIME DEFAULT GETDATE(),

    -- Constraint: Ép buộc định dạng email trường để ngăn user ảo
    CONSTRAINT CHK_User_Email CHECK (email LIKE '%@gm.uit.edu.vn')
);

-- 3. BẢNG SẢN PHẨM (Hàng hóa niêm yết)
CREATE TABLE PRODUCTS (
    product_id INT IDENTITY (1, 1) PRIMARY KEY,
    seller_id INT NOT NULL,
    category_id INT NOT NULL,
    title NVARCHAR(200) NOT NULL,
    description NVARCHAR(MAX),
    price DECIMAL(10, 2) NOT NULL,
    condition VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'Available',
    created_at DATETIME DEFAULT GETDATE(),

    FOREIGN KEY (seller_id) REFERENCES USERS (user_id),
    FOREIGN KEY (category_id) REFERENCES CATEGORIES (category_id),

    -- Constraint: Giá không được âm, kiểm soát trạng thái cứng
    CONSTRAINT CHK_Product_Price CHECK (price >= 0),
    CONSTRAINT CHK_Product_Condition CHECK (condition IN ('Brand New', 'Like New', 'Good', 'Fair')),
    CONSTRAINT CHK_Product_Status CHECK (status IN ('Available', 'Sold', 'Hidden'))
);

-- 4. BẢNG GIAO DỊCH (Bảng Fact cho Data Pipeline sau này)
CREATE TABLE TRANSACTIONS (
    transaction_id INT IDENTITY (1, 1) PRIMARY KEY,
    product_id INT NOT NULL,
    buyer_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'Pending',
    transaction_date DATETIME DEFAULT GETDATE(),

    FOREIGN KEY (product_id) REFERENCES PRODUCTS (product_id),
    FOREIGN KEY (buyer_id) REFERENCES USERS (user_id),

    CONSTRAINT CHK_Transaction_Amount CHECK (amount >= 0),
    CONSTRAINT CHK_Transaction_Status CHECK (status IN ('Pending', 'Completed', 'Cancelled'))
);
