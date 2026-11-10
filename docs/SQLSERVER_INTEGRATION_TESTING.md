# Kiểm thử tích hợp SQL Server — Step 7

## Mục tiêu

Bộ test backend hiện tại chạy trên SQLite in-memory. SQLite hữu ích để kiểm tra API và nghiệp vụ cơ bản, nhưng không chứng minh được hành vi của SQL Server đối với:

- Filtered unique index `UX_Transactions_ActiveProduct`.
- Các trigger cập nhật `updated_at`.
- Schema SQL Server thực tế sau khi áp dụng script/migration.

Step 7 bổ sung test SQL Server riêng, không thay thế bộ test SQLite hiện có.

## Rào chắn an toàn

Test SQL Server chỉ chạy khi đồng thời thỏa mãn:

1. `RUN_SQLSERVER_INTEGRATION=1`.
2. Có biến `SQLSERVER_TEST_DATABASE_URL`.
3. Tên database trong URL kết thúc bằng `_test`, ví dụ `ChoTroUIT_Step7_Test`.

Các test có ghi dữ liệu đều chạy trong transaction riêng và rollback khi kết thúc. Không dùng `DATABASE_URL` của ứng dụng để chọn database test. Không trỏ biến test vào database đang sử dụng hoặc database production.

## 1. Tạo database kiểm thử riêng

Trong SSMS, tạo database mới:

```sql
CREATE DATABASE ChoTroUIT_Step7_Test;
GO
```

Chọn database `ChoTroUIT_Step7_Test`, sau đó chạy `database_scripts/01_init_schema.sql`.

**Cảnh báo:** `01_init_schema.sql` xóa và tạo lại các bảng. Chỉ chạy trong database test mới tạo, tuyệt đối không chạy trên database có dữ liệu cần giữ.

Schema khởi tạo hiện tại đã bao gồm các cột xác nhận giao dịch và bảng REVIEWS. Không cần chạy tiếp hai migration Step 4/5 trên database vừa dựng bằng file init này. Hai migration chỉ dành cho database cũ được khởi tạo từ schema trước đó.

## 2. Cấu hình kết nối

Cài ODBC Driver 18 for SQL Server và dependencies của backend. Trong PowerShell, đặt URL trỏ trực tiếp đến database test. Ví dụ dùng Windows Authentication:

```powershell
$env:SQLSERVER_TEST_DATABASE_URL = "mssql+pyodbc://@localhost/ChoTroUIT_Step7_Test?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes"
$env:RUN_SQLSERVER_INTEGRATION = "1"
```

Với SQL Login, thay phần authority của URL bằng user/password tương ứng; mã hóa URL các ký tự đặc biệt trong password. Không đưa connection string hoặc password lên GitHub.

## 3. Chạy các bài kiểm thử

Từ thư mục gốc repository:

```powershell
# Backend: bộ test hiện tại trên SQLite
Set-Location backend
python -m pip install -r requirements-dev.txt
pytest -v

# Chỉ test tích hợp SQL Server trên database *_test
pytest -v -m sqlserver_integration

# Data pipeline: test logic ETL/analytics trên SQLite
Set-Location ..\data_pipeline
python -m pip install -r requirements-dev.txt
pytest -v

# Frontend: TypeScript check và production build
Set-Location ..\frontend
npm ci
npm run build
```

Khi chưa bật `RUN_SQLSERVER_INTEGRATION=1`, các test SQL Server sẽ được đánh dấu **SKIPPED** chứ không tự kết nối.

## 4. Phạm vi test SQL Server

| Test | Điều cần xác nhận |
|---|---|
| Schema/tables/columns | Đủ bảng và cột cần thiết cho Step 4/5 |
| Filtered unique index metadata | Index tồn tại, là UNIQUE và lọc bỏ trạng thái Cancelled |
| Trigger metadata | Ba trigger updated_at đang bật |
| Trigger behavior | UPDATE một user không truyền updated_at thì trigger tự cập nhật timestamp |
| Unique-index behavior | Có thể tạo giao dịch mới sau một giao dịch Cancelled; không thể tạo hai giao dịch chưa Cancelled cho cùng sản phẩm |

## 5. Phần cần xác nhận thủ công sau khi test tự động

- Xác nhận database hiện tại của dự án đã có migration Step 4 rồi Step 5 theo đúng thứ tự, nếu database được tạo từ schema cũ.
- Kiểm tra app kết nối bằng đúng `DATABASE_URL`, không phải `SQLSERVER_TEST_DATABASE_URL`.
- Chạy smoke test trên môi trường test: đăng ký/đăng nhập, đăng sản phẩm, buyer gửi yêu cầu, seller chấp nhận, hai bên xác nhận hoàn tất, review hai chiều và xem Account Center.
- Chỉ đánh dấu Step 7 hoàn tất khi có log test, kết quả build và xác nhận schema trên đúng SQL Server target.

## Ghi nhận kết quả

| Hạng mục | Kết quả | Bằng chứng / ghi chú |
|---|---|---|
| Backend pytest (SQLite) | Chưa chạy | |
| SQL Server integration tests | Chưa chạy | |
| Data pipeline pytest | Chưa chạy | |
| Frontend build | Chưa chạy | |
| SQL Server smoke test | Chưa chạy | |
