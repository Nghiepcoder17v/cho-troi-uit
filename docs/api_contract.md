# 📄 API Contract - Chợ Trời UIT (MVP)

Tài liệu này quy định các cổng giao tiếp (Endpoints) giữa Frontend và Backend. 
Tất cả các API yêu cầu xác thực phải gửi kèm Header: `Authorization: Bearer <token>`

---

## 1. Xác thực sinh viên (Authentication)
Dùng để đăng nhập hoặc đăng ký (nếu tài khoản chưa tồn tại). Hệ thống sẽ tự động bắt lỗi nếu email không thuộc trường UIT.

*   **Endpoint:** `POST /api/auth/login`
*   **Request Body (JSON):**
    ```json
    {
      "email": "25520001@gm.uit.edu.vn",
      "student_id": "25520001",
      "full_name": "Hà Văn Nghiệp"
    }
    ```
*   **Response (200 OK):**
    ```json
    {
      "status": "success",
      "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR...",
        "user_id": 1,
        "major": "Hệ thống thông tin"
      }
    }
    ```

---

## 2. Quản lý Sản phẩm (Products)

### A. Lấy danh sách sản phẩm (Có phân trang và bộ lọc)
*   **Endpoint:** `GET /api/products?category_id=2&status=Available&page=1`
*   **Response (200 OK):**
    ```json
    {
      "status": "success",
      "data": [
        {
          "product_id": 15,
          "title": "Bàn phím cơ ATK V75X",
          "price": 1200000.00,
          "condition": "Like New",
          "seller": {
            "user_id": 10,
            "full_name": "Nguyễn Văn A"
          }
        }
      ],
      "pagination": { "current_page": 1, "total_pages": 5 }
    }
    ```

### B. Đăng bán sản phẩm mới
*   **Endpoint:** `POST /api/products`
*   **Request Body (JSON):** *(Chú ý constraint: condition phải nằm trong tập cho phép, giá >= 0)*
    ```json
    {
      "category_id": 1,
      "title": "Giáo trình Cấu trúc dữ liệu và Giải thuật",
      "description": "Sách còn mới, tặng kèm đề cương ôn thi",
      "price": 45000.00,
      "condition": "Good"
    }
    ```
*   **Response (201 Created):**
    ```json
    {
      "status": "success",
      "message": "Product listed successfully",
      "data": { "product_id": 16 }
    }
    ```

---

## 3. Quản lý Giao dịch (Transactions)
Chốt đơn mua một món hàng. Bảng này sẽ sinh ra dữ liệu phục vụ báo cáo phân tích DE.

*   **Endpoint:** `POST /api/transactions`
*   **Request Body (JSON):**
    ```json
    {
      "product_id": 15,
      "amount": 1150000.00 
    }
    ```
    *(Ghi chú: `amount` là giá chốt cuối cùng, có thể thấp hơn giá niêm yết do sinh viên mặc cả. `buyer_id` sẽ được lấy tự động từ Token xác thực).*
*   **Response (201 Created):**
    ```json
    {
      "status": "success",
      "data": {
        "transaction_id": 81,
        "status": "Pending"
      }
    }
    ```