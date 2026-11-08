# 📄 API Contract - Chợ Trời UIT (MVP)

Tài liệu này quy định các cổng giao tiếp giữa Frontend và Backend. **Swagger tự sinh** (luôn đúng với code): `http://localhost:8000/docs`.

## Quy ước chung

- Dữ liệu vào/ra là JSON. Thành công luôn có dạng `{"status": "success", "data": ..., "message"?: ...}`.
- API cần đăng nhập phải gửi header `Authorization: Bearer <token>`. Danh tính (`seller_id`, `buyer_id`) **luôn lấy từ token**, không nhận từ client.
- Lỗi theo chuẩn FastAPI: `{"detail": "<thông báo>"}` (lỗi validate `422` có `detail` là danh sách chi tiết từng trường).
- Thời gian là **UTC**, định dạng ISO-8601. Tiền (VND) trả về dạng **số**, không phải chuỗi.

| Mã | Ý nghĩa |
|----|---------|
| 400 | Vi phạm quy tắc nghiệp vụ (tự mua hàng của mình, giá chốt > giá niêm yết...) |
| 401 | Thiếu / sai / hết hạn token, hoặc sai email/mật khẩu |
| 404 | Không tìm thấy (sản phẩm, danh mục). Sản phẩm `Hidden` cũng trả 404 |
| 409 | Xung đột (email/MSSV đã đăng ký; sản phẩm đã bán) |
| 422 | Dữ liệu gửi lên không hợp lệ |

---

## 1. Xác thực (Authentication)

### Đăng ký — `POST /api/auth/register`
Chỉ nhận email `@gm.uit.edu.vn`; MSSV (8 chữ số) phải trùng phần trước `@`; mật khẩu 8–72 byte.
```json
{
  "email": "25520001@gm.uit.edu.vn",
  "student_id": "25520001",
  "full_name": "Hà Văn Nghiệp",
  "major": "Hệ thống thông tin",
  "password": "Matkhau123"
}
```
**201 Created**
```json
{ "status": "success", "message": "Đăng ký thành công",
  "data": { "user_id": 1, "student_id": "25520001", "email": "25520001@gm.uit.edu.vn",
            "full_name": "Hà Văn Nghiệp", "major": "Hệ thống thông tin", "created_at": "2026-11-08T12:00:00" } }
```
Lỗi: `409` (email/MSSV đã tồn tại), `422` (sai định dạng).

### Đăng nhập — `POST /api/auth/login`
```json
{ "email": "25520001@gm.uit.edu.vn", "password": "Matkhau123" }
```
**200 OK**
```json
{ "status": "success",
  "data": { "token": "eyJhbGciOi...", "token_type": "bearer", "user_id": 1, "major": "Hệ thống thông tin" } }
```
Lỗi: `401` (sai email hoặc mật khẩu — cùng một thông báo cho cả hai).

### Thông tin tài khoản — `GET /api/users/me` 🔒
Trả về `{"status": "success", "data": { ...như phần data khi đăng ký... }}`.

---

## 2. Danh mục & Sản phẩm

### `GET /api/categories`
```json
{ "status": "success", "data": [ { "category_id": 1, "category_name": "Giáo trình" } ] }
```

### Danh sách sản phẩm — `GET /api/products`
| Tham số | Mặc định | Ghi chú |
|---|---|---|
| `category_id` | — | lọc theo danh mục |
| `status` | `Available` | `Available` hoặc `Sold` (`Hidden` → 400) |
| `q` | — | tìm theo tiêu đề (chứa từ khoá, không phân biệt hoa thường) |
| `page` | 1 | ≥ 1 |
| `page_size` | 20 | 1–100 |

Sắp xếp mới nhất trước. **200 OK**
```json
{ "status": "success",
  "data": [ { "product_id": 15, "category_id": 3, "title": "Bàn phím cơ ATK V75X", "description": null,
              "price": 1200000.0, "condition": "Like New", "status": "Available",
              "created_at": "2026-11-01T09:30:00",
              "seller": { "user_id": 10, "full_name": "Nguyễn Văn A" } } ],
  "pagination": { "current_page": 1, "page_size": 20, "total_items": 87, "total_pages": 5 } }
```

### Chi tiết — `GET /api/products/{product_id}`
`{"status": "success", "data": { ...một sản phẩm như trên... }}`. `404` nếu không tồn tại hoặc đã ẩn.

### Đăng bán — `POST /api/products` 🔒
`condition` ∈ `Brand New | Like New | Good | Fair`; `0 ≤ price ≤ 99999999.99`.
```json
{ "category_id": 1, "title": "Giáo trình Cấu trúc dữ liệu và Giải thuật",
  "description": "Sách còn mới, tặng kèm đề cương ôn thi", "price": 45000, "condition": "Good" }
```
**201 Created**
```json
{ "status": "success", "message": "Product listed successfully", "data": { "product_id": 16 } }
```
Lỗi: `401`, `404` (danh mục không tồn tại), `422`.

---

## 3. Giao dịch (Transactions) 🔒

### Đặt mua — `POST /api/transactions`
Chốt đơn **ngay lập tức** (MVP chưa có bước xác nhận): sản phẩm chuyển `Available → Sold` và tạo giao dịch `Completed` trong cùng một lần commit. `amount` là giá chốt, được phép thấp hơn giá niêm yết (mặc cả) nhưng **không được cao hơn**.
```json
{ "product_id": 15, "amount": 1150000 }
```
**201 Created**
```json
{ "status": "success", "message": "Đặt mua thành công",
  "data": { "transaction_id": 81, "product_id": 15, "amount": 1150000.0,
            "status": "Completed", "transaction_date": "2026-11-08T12:30:00" } }
```
Lỗi: `400` (tự mua hàng của mình / giá chốt > giá niêm yết), `404`, `409` (đã có người mua trước), `422`.
