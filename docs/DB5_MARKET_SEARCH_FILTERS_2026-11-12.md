# DB-5 / FE-2 — Bộ lọc và sắp xếp Explore

**Ngày:** 12/11/2026  
**Branch:** `feat/market-search-filters`  
**Phạm vi:** Bổ sung API tìm kiếm/lọc/sắp xếp và kết nối bộ điều khiển trên trang Explore. Không thay đổi schema, không tạo migration và không ghi dữ liệu vào SQL Server.

## 1. API `GET /api/products`

Các tham số mới:

| Tham số | Hành vi |
|---|---|
| `condition` | Lọc chính xác theo `Brand New`, `Like New`, `Good`, `Fair` |
| `min_price` | Giá tối thiểu, bao gồm biên; từ 0 đến `99999999.99`, tối đa 2 chữ số thập phân |
| `max_price` | Giá tối đa, bao gồm biên; cùng giới hạn với `min_price` |
| `sort` | `newest` (mặc định), `price_asc`, `price_desc` |

Quy tắc:

- Giá trị `min_price` không được lớn hơn `max_price`; trường hợp vi phạm trả HTTP 422.
- Bộ lọc được áp dụng trong truy vấn SQLAlchemy trước khi đếm tổng và phân trang.
- Sort theo giá dùng `created_at DESC, product_id DESC` làm tie-breaker để kết quả ổn định.
- Public listing vẫn chỉ trả `Available`. Các quy tắc chặn `Reserved`, `Sold`, `Hidden` được giữ nguyên.
- Truy vấn dùng biểu thức SQLAlchemy có tham số, không ghép chuỗi SQL từ input.
- Chưa thêm index mới: chưa có workload/plan thực tế chứng minh index nào cần thiết; tránh thêm index theo suy đoán.

## 2. Explore frontend

- Bổ sung chọn tình trạng, giá tối thiểu/tối đa và kiểu sắp xếp.
- Nút **Áp dụng bộ lọc** gửi các điều kiện lên API; không lọc client trên trang kết quả đã phân trang.
- Tìm kiếm từ khóa vẫn chỉ gửi khi nhấn Tìm kiếm/Enter.
- Danh mục tiếp tục áp dụng ngay như hành vi hiện có.
- Xóa bộ lọc reset cả giá trị đang nhập và bộ lọc đang áp dụng.
- Trạng thái kết quả, số lượng tin và pagination lấy từ response API.
- CSS có breakpoint cho desktop, tablet và mobile; các trường có label và focus-visible state.

## 3. Kiểm thử được bổ sung

Trong `backend/tests/test_products.py`:

- Kết hợp condition + min/max price; xác nhận giới hạn giá là inclusive.
- Xác nhận pagination được tính sau khi lọc.
- Kiểm tra sort tăng/giảm theo giá và tie-breaker khi bằng giá.
- Từ chối condition/sort không hợp lệ, min lớn hơn max và giá có quá 2 chữ số thập phân.
- Các test hiện có tiếp tục bao phủ search, category pagination, status public, hidden/reserved và ownership.

## 4. Phạm vi không thực hiện

- Không thay đổi schema/ORM table hoặc migration.
- Không thêm index khi chưa có bằng chứng workload.
- Không thay đổi trạng thái sản phẩm, quyền truy cập, luồng giao dịch hay ETL.
- Chưa chạy browser QA theo kế hoạch đã thống nhất.
- Chưa xác minh schema SQL Server trực tiếp; test CI backend hiện dùng SQLite in-memory và không thay thế SQL Server integration test.

## 5. Kiểm tra và nghiệm thu

Tại thời điểm tạo báo cáo, CI của PR chưa được xác nhận hoàn tất. Chỉ cập nhật kết quả sau khi GitHub Actions trả trạng thái thực tế. Browser QA và SQL Server verification tiếp tục là các việc còn chờ chủ dự án chạy trong môi trường local.

