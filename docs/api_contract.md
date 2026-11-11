# 📄 API Contract - Chợ Trời UIT (MVP)

Tài liệu này quy định các cổng giao tiếp giữa Frontend và Backend. **Swagger tự sinh** (luôn đúng với code): `http://localhost:8000/docs`.

## Quy ước chung

- Dữ liệu vào/ra là JSON. Thành công luôn có dạng `{"status": "success", "data": ..., "message"?: ...}`.
- API cần đăng nhập dùng JWT trong cookie `access_token` do backend đặt với các cờ `HttpOnly`, `Secure`, `SameSite=Lax`. Frontend gửi cookie bằng `credentials: "include"`; token không xuất hiện trong JSON hoặc JavaScript storage. Danh tính (`seller_id`, `buyer_id`) **luôn lấy từ token**, không nhận từ client.
- Lỗi theo chuẩn FastAPI: `{"detail": "<thông báo>"}` (lỗi validate `422` có `detail` là danh sách chi tiết từng trường).
- Thời gian là **UTC**, định dạng ISO-8601. Tiền (VND) trả về dạng **số**, không phải chuỗi.

| Mã | Ý nghĩa |
|----|---------|
| 400 | Vi phạm quy tắc nghiệp vụ (tự mua hàng của mình, giá đề nghị > giá niêm yết...) |
| 401 | Thiếu / sai / hết hạn token, hoặc sai email/mật khẩu |
| 403 | Người dùng không có quyền thực hiện hành động (ví dụ không tham gia giao dịch, sửa review của người khác) |
| 404 | Không tìm thấy (sản phẩm, danh mục, người dùng, review). Sản phẩm `Hidden` cũng trả 404 |
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
{ "status": "success", "data": { "user_id": 1, "major": "Hệ thống thông tin" } }
```
Đồng thời trả `Set-Cookie: access_token=...; HttpOnly; Secure; SameSite=Lax; Path=/`.
Lỗi: `401` (sai email hoặc mật khẩu — cùng một thông báo cho cả hai).

### Đăng xuất — `POST /api/auth/logout`
Xóa cookie phiên bằng `Set-Cookie` hết hạn. Khi gửi từ trình duyệt, request phải
có `Origin` nằm trong `CORS_ORIGINS`; cookie được gửi tự động cùng request.

### Thông tin tài khoản — `GET /api/users/me` 🔒
Trả về thông tin tài khoản hiện tại, gồm email và MSSV; endpoint này yêu cầu
cookie phiên hợp lệ.

### Cập nhật hồ sơ cá nhân — `PATCH /api/users/me` 🔒
Chỉ cập nhật `full_name` và `major`; email và MSSV không thể thay đổi qua endpoint
này. Gửi `major: null` để xóa ngành học.
```json
{ "full_name": "Nguyễn Văn A", "major": "Kỹ thuật phần mềm" }
```
Trả về user hiện tại sau cập nhật. Body rỗng hoặc gửi các trường ngoài phạm vi
sẽ bị từ chối.

### Đổi mật khẩu — `POST /api/users/me/change-password` 🔒
Phải gửi mật khẩu hiện tại để xác minh; mật khẩu mới dài tối thiểu 8 ký tự và
tối đa 72 byte UTF-8.
```json
{ "current_password": "MatkhauCu123", "new_password": "MatkhauMoi123" }
```
Lỗi `400` nếu mật khẩu hiện tại không chính xác; `422` nếu dữ liệu mới không hợp lệ.

### Trang cá nhân công khai — `GET /api/users/{user_id}/public-profile`
Trả về `user_id`, họ tên, ngành học, ngày tham gia, điểm uy tín, số review và
số giao dịch hoàn tất. Không trả email, MSSV hoặc dữ liệu xác thực.

### Tin đăng công khai của người dùng — `GET /api/users/{user_id}/products`
Trả về tin `Available` và `Sold` của người dùng, hỗ trợ phân trang và bộ lọc
`status=Available|Sold`. Tin `Hidden` và `Reserved` không xuất hiện trên
trang cá nhân công khai.

### Điểm uy tín — `GET /api/users/{user_id}/reputation`
Điểm là trung bình cộng của các đánh giá thật mà người dùng nhận được, làm tròn
một chữ số thập phân. Khi chưa có đánh giá, `score` là `null`,
`review_count` bằng 0 và nhãn là `Chưa có đánh giá`. `rating_distribution`
luôn có số lượng cho từng mức 1–5. Các trường `completed_sales` và
`total_sales` tiếp tục phản ánh lịch sử bán hàng của người dùng.

### Danh sách đánh giá nhận được — `GET /api/users/{user_id}/reviews`
Endpoint công khai, trả về đánh giá thật theo thời gian mới nhất trước; mỗi
mục gồm người đánh giá, sản phẩm, điểm, bình luận và thời điểm tạo/cập nhật.

### Gửi đánh giá — `POST /api/transactions/{transaction_id}/reviews` 🔒
Chỉ buyer hoặc seller của giao dịch `Completed` được đánh giá người còn lại.
Mỗi bên chỉ có một đánh giá trên mỗi giao dịch. Client chỉ gửi `rating` từ 1
đến 5 và `comment` tùy chọn tối đa 1000 ký tự; danh tính hai bên được lấy từ
JWT và giao dịch, không nhận từ client.

### Sửa đánh giá — `PATCH /api/reviews/{review_id}` 🔒
Chỉ tác giả được sửa đánh giá của mình. Có thể cập nhật `rating`, `comment`
hoặc cả hai; gửi `comment: null` để xóa nội dung bình luận. Không có API xóa
đánh giá trong Step 5.

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

Trường `my_review` trong lịch sử mua/bán trả về đánh giá do tài khoản hiện
tại viết cho giao dịch đó, hoặc `null` nếu chưa đánh giá.

Trạng thái nghiệp vụ:

- Transaction: `Pending → Accepted → Completed`, hoặc `Pending/Accepted → Cancelled`.
- Product: `Available → Reserved → Sold`; từ `Reserved` về `Available` khi
  seller từ chối hoặc một bên hủy.
- Chỉ giao dịch `Completed` mới đủ điều kiện đánh giá. Các giao dịch
  `Completed` có từ trước Step 5 cũng được đánh giá; timestamp xác nhận cũ
  không bắt buộc phải có.
