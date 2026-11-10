# 📄 API Contract - Chợ Trời UIT (MVP)

Tài liệu này quy định các cổng giao tiếp giữa Frontend và Backend. **Swagger tự sinh** (luôn đúng với code): `http://localhost:8000/docs`.

## Quy ước chung

- Dữ liệu vào/ra là JSON. Thành công luôn có dạng `{"status": "success", "data": ..., "message"?: ...}`.
- API cần đăng nhập phải gửi header `Authorization: Bearer <token>`. Danh tính (`seller_id`, `buyer_id`) **luôn lấy từ token**, không nhận từ client.
- Lỗi theo chuẩn FastAPI: `{"detail": "<thông báo>"}` (lỗi validate `422` có `detail` là danh sách chi tiết từng trường).
- Thời gian là **UTC**, định dạng ISO-8601. Tiền (VND) trả về dạng **số**, không phải chuỗi.

| Mã | Ý nghĩa |
|----|---------|
| 400 | Vi phạm quy tắc nghiệp vụ (tự mua hàng của mình, giá đề nghị > giá niêm yết...) |
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

### Điểm uy tín người bán — `GET /api/users/{user_id}/reputation`
Hiện trả về số giao dịch hoàn tất và tổng số giao dịch. `score` là `null` và nhãn
là `Chưa có đánh giá thật`; không hiển thị điểm uy tín tự sinh. Review thật sẽ
được bổ sung ở Step 5 và chỉ áp dụng cho giao dịch `Completed`.

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
| `status` | `Available` | Chỉ `Available` được liệt kê công khai; giá trị khác → 400 |
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

### Sản phẩm của tôi — `GET /api/products/mine` 🔒
Trả về các sản phẩm do người dùng hiện tại đăng. Hỗ trợ `status`, `page` và
`page_size`; sản phẩm `Hidden` chỉ xuất hiện ở endpoint riêng này khi người dùng
là chủ sở hữu.

### Cập nhật hoặc ẩn sản phẩm — `PATCH /api/products/{product_id}` 🔒
Chỉ chủ sở hữu mới có thể cập nhật. Có thể cập nhật `category_id`, `title`,
`description`, `price`, `condition` và `status`. Sản phẩm `Reserved` hoặc `Sold` không thể
chỉnh sửa. Chủ sở hữu vẫn có thể xem `Reserved` trong `/api/products/mine`.
`status` chỉ được chuyển giữa `Available` và `Hidden`; không thể tự chuyển tin
đăng thành `Sold` nếu không có giao dịch.

---

## 3. Giao dịch (Transactions) 🔒

### Gửi yêu cầu mua — `POST /api/transactions`
Người mua gửi yêu cầu; sản phẩm chuyển `Available → Reserved` và giao dịch
được tạo ở trạng thái `Pending` trong cùng transaction. Seller phải chấp nhận
hoặc từ chối yêu cầu. `amount` được phép thấp hơn giá niêm yết nhưng không được
cao hơn.
```json
{ "product_id": 15, "amount": 1150000 }
```
**201 Created** trả về transaction `Pending`, hai trường
`buyer_confirmed_at` và `seller_confirmed_at` ban đầu là `null`.
Lỗi: `400` (tự mua / giá cao hơn niêm yết), `404`, `409` (không còn Available
hoặc đã được giữ chỗ), `422`.

### Seller chấp nhận — `POST /api/transactions/{transaction_id}/accept` 🔒
Chỉ seller của sản phẩm được chuyển `Pending → Accepted`. Sản phẩm vẫn ở
trạng thái `Reserved`.

### Seller từ chối — `POST /api/transactions/{transaction_id}/reject` 🔒
Chỉ seller được từ chối giao dịch `Pending`. Giao dịch thành `Cancelled`, sản
phẩm quay về `Available`.

### Một bên hủy — `POST /api/transactions/{transaction_id}/cancel` 🔒
Buyer hoặc seller có thể hủy giao dịch ở `Pending` hoặc `Accepted`. Nếu một
bên đã xác nhận trước đó thì timestamp đó cũng bị xóa; sản phẩm được mở bán lại.
Không thể hủy giao dịch `Completed`.

### Xác nhận hoàn tất — `POST /api/transactions/{transaction_id}/confirm-completion` 🔒
Buyer và seller phải tự xác nhận riêng sau khi tự bàn giao/thanh toán bên ngoài
nền tảng. Xác nhận đầu tiên lưu timestamp nhưng giao dịch vẫn là `Accepted`.
Chỉ khi cả hai bên xác nhận, giao dịch mới thành `Completed` và sản phẩm thành
`Sold`. Một tài khoản không thể xác nhận thay bên kia.

### Lịch sử — `GET /api/transactions/purchases` và `GET /api/transactions/sales` 🔒
Trả về các giao dịch buyer/seller tham gia, trạng thái, thông tin hai bên và
hai timestamp xác nhận.

Trạng thái nghiệp vụ:

- Transaction: `Pending → Accepted → Completed`, hoặc `Pending/Accepted → Cancelled`.
- Product: `Available → Reserved → Sold`; từ `Reserved` về `Available` khi
  seller từ chối hoặc một bên hủy.
- Chỉ giao dịch `Completed` mới đủ điều kiện đánh giá ở Step 5.
