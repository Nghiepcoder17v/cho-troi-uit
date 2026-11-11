# SCD Type 2 cho dimension sản phẩm

Step này nâng `dim_product` lên SCD Type 2 để báo cáo giao dịch giữ được thuộc tính tin đăng tại thời điểm giao dịch. `dim_user` và `dim_date` vẫn là SCD Type 1.

## Cách lưu lịch sử

Mỗi phiên bản có `effective_from`, `effective_to` và `is_current`. Khoảng hiệu lực là nửa kín `[effective_from, effective_to)`: một phiên bản hết hiệu lực đúng thời điểm phiên bản kế tiếp bắt đầu. Unique filtered index bảo đảm mỗi `product_id` chỉ có một phiên bản hiện hành.

ETL tạo phiên bản mới khi một trong các trường phân tích thay đổi: danh mục, tên danh mục, tiêu đề, tình trạng, giá niêm yết hoặc trạng thái tin. Fact chọn `product_key` có khoảng hiệu lực chứa `transaction_at`, nên báo cáo lịch sử không bị đổi theo phiên bản hiện tại. Đổi tên danh mục được ghi nhận tại thời điểm ETL quan sát thay đổi vì bảng `categories` chưa có `updated_at`.

SCD2 chỉ lưu các phiên bản được quan sát từ lúc bật tính năng. OLTP hiện chỉ giữ trạng thái mới nhất của sản phẩm, không có CDC/audit log; do đó ETL không thể tái tạo những lần sửa tin đã xảy ra trước lần chạy đầu tiên sau khi áp dụng migration. `--full-refresh` đọc lại nguồn nhưng không xóa lịch sử SCD2.

## Nâng cấp DWH đã tồn tại

Database DWH mới được tạo trực tiếp theo schema mới. Với DWH đã có `dim_product` kiểu cũ, hãy sao lưu DWH và chạy migration một lần trong `ChoTroUIT_DWH` trước khi khởi động API/ETL bản mới:

```powershell
sqlcmd -S localhost -d ChoTroUIT_DWH -E -b -i database_scripts/migrations/20261111_dwh_product_scd2.sql
```

Điều chỉnh `-S` và xác thực theo môi trường. Nếu dùng SQL Authentication, thêm `-U` và nhập mật khẩu theo chính sách vận hành; đừng ghi mật khẩu vào shell history hoặc tài liệu. Migration giữ nguyên hàng dimension và fact hiện có, gán mỗi hàng cũ một phiên bản bắt đầu từ `listed_at`, bỏ unique constraint cũ trên `product_id`, rồi tạo unique filtered index cho hàng hiện hành. Script có thể chạy lại an toàn.

ETL kiểm tra các cột SCD2 khi khởi tạo và dừng với hướng dẫn migration nếu phát hiện DWH cũ chưa được nâng cấp. Không dùng `--drop-dwh` để nâng cấp.

## Theo dõi

Số lượng sản phẩm đối chiếu với OLTP theo số `product_id` phân biệt; số phiên bản lịch sử có thể lớn hơn số tin nguồn.

```sql
SELECT product_id, product_key, title, category_name, current_status,
       effective_from, effective_to, is_current
FROM dbo.dim_product
WHERE product_id = @product_id
ORDER BY effective_from;

SELECT product_id, COUNT(*) AS version_count
FROM dbo.dim_product
GROUP BY product_id
HAVING COUNT(*) > 1
ORDER BY version_count DESC;
```

Schema được phản chiếu ở [star schema](dwh_star_schema.dbml); ETL kiểm thử lịch sử và khóa dimension theo thời điểm sự kiện trong `data_pipeline/tests/test_etl_pipeline.py`.
