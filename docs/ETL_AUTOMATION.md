# Tự động chạy ETL

Step 9 bổ sung scheduler chạy ETL theo chu kỳ trong Compose. Scheduler là profile riêng nên không tự bật khi chỉ chạy marketplace.

## Bật và theo dõi

Tạo `.env.compose` từ `.env.compose.example` như hướng dẫn trong [Docker Compose](DOCKER_COMPOSE.md), sau đó chạy từ thư mục gốc:

```powershell
docker compose --env-file .env.compose --profile automation up -d etl-scheduler
docker compose --env-file .env.compose logs -f etl-scheduler
docker compose --env-file .env.compose ps etl-scheduler
```

Scheduler chạy ngay một chu kỳ khi khởi động. Sau khi chu kỳ kết thúc, nó chờ khoảng cấu hình rồi chạy tiếp; các chu kỳ không chồng lấn trong cùng instance. Dùng `docker compose ... stop etl-scheduler` để dừng. Khởi động lại sẽ chạy ngay một lượt; watermark và upsert cho phép chạy lại an toàn.

Log chi tiết được ghi ra stdout và giữ theo log driver Docker với giới hạn 10 MB × 3 file. Mỗi lần ETL cũng có dòng trạng thái (`RUNNING`, `SUCCESS`, `WARNING` hoặc `FAILED`) trong bảng `etl_run_log`; watermark nằm ở `etl_watermark`, dòng bị từ chối ở `etl_rejected_rows`.

Xem lịch sử mới nhất trực tiếp trên DWH:

```sql
SELECT TOP (20)
    run_id, mode, status, started_at, finished_at,
    users_extracted, products_extracted, transactions_extracted,
    rows_rejected, message
FROM dbo.etl_run_log
ORDER BY run_id DESC;

SELECT source_table, last_updated_at, last_run_id
FROM dbo.etl_watermark
ORDER BY source_table;
```

## Cấu hình

Đặt các giá trị trong `.env.compose` trước khi chạy service:

| Biến | Mặc định | Ý nghĩa |
| --- | ---: | --- |
| `ETL_INTERVAL_SECONDS` | `3600` | Thời gian chờ sau mỗi chu kỳ hoàn tất |
| `ETL_RETRY_ATTEMPTS` | `3` | Số lần retry thêm sau lần thử đầu; cho phép `0` |
| `ETL_RETRY_DELAY_SECONDS` | `30` | Thời gian chờ trước retry đầu tiên |
| `ETL_MAX_RETRY_DELAY_SECONDS` | `300` | Trần backoff tăng theo cấp số nhân |
| `ETL_OVERLAP_MINUTES` | `5` | Cửa sổ overlap để bắt commit trễ |

Nếu hết số lần retry, scheduler ghi lỗi cuối cùng ra stdout, để bản ghi `FAILED` trong DWH (khi kết nối DWH còn hoạt động), rồi chờ chu kỳ kế tiếp. Trạng thái `WARNING` được ghi log và không retry ngay vì thường cần xử lý dữ liệu nguồn/quarantine trước.

## Chống chạy đồng thời và nạp trùng

Trước mỗi chu kỳ, scheduler lấy khóa ứng dụng độc quyền `cho-troi-uit:etl:scheduler` trong database DWH bằng `sp_getapplock`. Nếu một instance khác đang giữ khóa, instance này bỏ qua lượt đó. Khóa được giải phóng sau chu kỳ hoặc khi kết nối SQL đóng. Không scale service scheduler nếu chưa xác minh cơ chế khóa trên cấu hình SQL Server đích.

Pipeline hiện nạp dimension/fact và cập nhật watermark trong cùng transaction DWH. Cửa sổ overlap có thể đọc lại dòng; lần chạy lại không tạo fact trùng hoặc phiên bản sản phẩm mới nếu thuộc tính không đổi. Mỗi retry có `run_id` riêng để giữ lịch sử audit. Không dùng `--drop-dwh` trong scheduler.

Nếu nâng từ DWH cũ, cần áp dụng migration [SCD Type 2](../database_scripts/migrations/20261111_dwh_product_scd2.sql) trước khi bật scheduler. Chi tiết migration và giới hạn lịch sử xem [DWH SCD2](DWH_SCD2.md).

## Kiểm tra thủ công

Sau khi bật service, xác nhận:

1. `docker compose ... ps` hiển thị scheduler đang chạy.
2. Log cho thấy `run_id`, mode, trạng thái, số dòng trích xuất/nạp và kết quả đối soát.
3. `etl_run_log` có bản ghi hoàn tất và watermark được cập nhật.
4. Chạy lại ETL không làm tăng số fact/dimension khi nguồn không đổi.
5. Dừng scheduler không xóa dữ liệu DWH; chạy lại tiếp tục từ watermark đã lưu.

## Step 9 verification record

Verified with a dedicated local Compose project and disposable SQL Server volume. The scheduler ran every 15 seconds for the smoke check:

- The initial cycle loaded 10 users, 10 products, and 5 transactions with status `SUCCESS`; reconciliation matched the source and DWH counts.
- Several incremental cycles completed with `SUCCESS`. Because the overlap re-read the latest changed row, each cycle updated existing dimension/fact rows; the final counts remained 10, 10, and 5, with no duplicate fact or dimension rows.
- A separate temporary scheduler used a deliberately nonexistent source database. It made three attempts total, logged three `FAILED` run records, waited 1 then 2 seconds between retries, and returned to its scheduled wait instead of exiting.
- Scheduler runs acquired and released the SQL Server application lock successfully. DWH watermark and run history remained present across cycles.
- The isolated Compose containers and volume were removed after verification; no project database was used for this check.
