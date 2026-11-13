# Kiểm thử tích hợp SQL Server — Step 7

## Mục tiêu

Tên database chuẩn của dự án là `ChoTroUIT` (OLTP) và `ChoTroUIT_DWH` (DWH).
`UIT_Exchange` được nhắc trong phần kết quả bên dưới chỉ là tên database của
môi trường cá nhân đã dùng để xác minh migration; nó không phải tên mặc định
của dự án hay tên database kiểm thử.

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

## 5. DB-6A — Favorites migration và HTTP API trên SQL Server

DB-6A thêm dbo.USER_FAVORITES bằng migration cộng thêm
database_scripts/migrations/20261113_user_favorites.sql. Bài test này cần
một database mới có hậu tố _test; không chạy migration hoặc test ghi dữ liệu
trên ChoTroUIT, UIT_Exchange, DWH hay database đang dùng.

### 5.1 Dựng database thử nghiệm

Trong SSMS, tạo một database mới, ví dụ:

```sql
CREATE DATABASE ChoTroUIT_DB6A_Test;
GO
```

Chọn đúng database ChoTroUIT_DB6A_Test, sau đó chạy lần lượt:

1. database_scripts/01_init_schema.sql — chỉ trên database test mới vừa tạo.
2. database_scripts/migrations/20261113_user_favorites.sql.

**Không chạy lại 01_init_schema.sql trên database đã có dữ liệu.** File này
xóa và tạo lại schema. Với database kiểm thử đã tồn tại, chỉ chạy migration
Favorites nếu baseline schema đã được xác nhận tương thích.

### 5.2 Cấu hình và chạy SQL Server integration tests

Từ thư mục backend trong PowerShell:

```powershell
$env:SQLSERVER_TEST_DATABASE_URL = "mssql+pyodbc://@localhost/ChoTroUIT_DB6A_Test?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes"
$env:RUN_SQLSERVER_INTEGRATION = "1"

python -m pytest -v -m sqlserver_integration
```

Với SQL Login, dùng user/password phù hợp và URL-encode ký tự đặc biệt.
Không commit connection string hoặc thông tin đăng nhập vào repository.

### 5.3 Kiểm thử SQL Server tự động trên GitHub Actions

Workflow .github/workflows/sqlserver-integration.yml tạo SQL Server 2022
Developer container dùng một lần cho PR/push có thay đổi trong backend hoặc
database_scripts. Workflow tự tạo ChoTroUIT_DB6A_Test, áp dụng 01_init_schema.sql
chỉ trong database container đó, sau đó áp dụng migration Favorites hai lần
để kiểm tra khả năng chạy lặp và chạy toàn bộ marker sqlserver_integration.

Workflow này không kết nối DATABASE_URL của ứng dụng hoặc database bên ngoài.
Có thể chạy thủ công từ tab Actions bằng workflow_dispatch. Kết quả workflow
được tách biệt với CI thường; không xem các bài SQL Server là đạt nếu workflow
này chưa chạy thành công.

### Phạm vi DB-6A được kiểm tra


| Test | Điều cần xác nhận |
|---|---|
| Favorites schema | Đúng ba cột, kiểu dữ liệu, nullability và composite PK (user_id, product_id) |
| Foreign keys | FK đến USERS/PRODUCTS, không cascade delete |
| Pagination index | user_id ASC, created_at DESC, product_id DESC |
| UTC default | created_at dùng SYSUTCDATETIME() |
| Constraint behavior | Chặn favorite trùng và product FK không hợp lệ |
| HTTP API trên SQL Server | FastAPI GET/PUT/DELETE chạy qua engine/pool SQL Server riêng; xác minh query hint SQL Server, auth, idempotency, ownership, dữ liệu được che, tombstone Hidden và không tạo TRANSACTIONS |

Bài HTTP API dùng engine/pool SQL Server riêng cho các request chạy ở worker thread.
Dữ liệu được tạo trước test và xóa tường minh trong finally theo thứ tự phụ thuộc khóa
ngoại. URL vẫn bắt buộc trỏ đến database có hậu tố _test; không dùng database ứng dụng.

## 6. Phần cần xác nhận thủ công sau khi test tự động

- Database theo cấu hình `DATABASE_URL` là `UIT_Exchange`. Metadata ban đầu cho thấy thiếu hai cột xác nhận và bảng `REVIEWS`; đã tạo backup `COPY_ONLY`, xác minh bằng `RESTORE VERIFYONLY`, rồi chạy migration Step 4 trước Step 5.
- Sau migration, đã xác nhận `buyer_confirmed_at`, `seller_confirmed_at`, bảng `REVIEWS`, các constraint/index của review và filtered unique index. Ba trigger `updated_at` vẫn bật.
- Integration test, API smoke test và UI smoke test đều chạy trên `ChoTroUIT_Step7_Test`, không ghi dữ liệu kiểm thử vào `UIT_Exchange`.
- Step 7 chỉ hoàn tất sau khi có log test, kết quả build và xác nhận schema trên SQL Server target; các điều kiện đó hiện đã được đáp ứng cho môi trường cục bộ đã kiểm tra.

## Ghi nhận kết quả

| Hạng mục | Kết quả | Bằng chứng / ghi chú |
|---|---|---|
| Backend pytest (SQLite) | Passed | 66 passed, 3 skipped (các test SQL Server được skip trong lần chạy toàn bộ backend) |
| SQL Server integration tests | Passed | 3 passed trên `ChoTroUIT_Step7_Test`; test schema, trigger `updated_at` và filtered unique index |
| Data pipeline pytest | Passed | 61 passed; gồm initial/incremental/full refresh, idempotency, watermark, reconciliation và analytics |
| Frontend build | Passed | `npm run build`; TypeScript và Vite production build thành công |
| SQL Server API smoke test | Passed | 37 kiểm tra qua TestClient trên SQL Server test database; bao gồm auth, profile, privacy, product lifecycle, giao dịch, hủy và review |
| Account Center UI smoke test | Passed | 14 kiểm tra bằng Chrome trên app nối tới `ChoTroUIT_Step7_Test`; gồm hồ sơ, privacy, quản lý tin, giỏ hàng, đơn mua/bán, theme và đổi mật khẩu |
| Trạng thái migration database dự án | Verified | `UIT_Exchange`: backup COPY_ONLY đã verify; migrations Step 4 rồi Step 5 chạy thành công; metadata sau migration đầy đủ |


## 7. DB-6A SQL Server CI result — 2026-11-13

- [SQL Server integration workflow #3](https://github.com/Nghiepcoder17v/cho-troi-uit/actions/runs/43408035840): **Success**. It created a new `ChoTroUIT_DB6A_Test` database inside an ephemeral SQL Server 2022 Developer container, applied `01_init_schema.sql` only in that new container database, applied the Favorites migration twice, and ran all SQL Server integration tests.
- Result: **6 passed, 89 deselected**. The six tests covered schema/columns/indexes/triggers, updated_at behavior, student ID constraint, filtered unique transaction index, Favorites composite PK/FKs/default/index, and a FastAPI Favorites HTTP round trip against SQL Server.
- [Standard CI run #73](https://github.com/Nghiepcoder17v/cho-troi-uit/actions/runs/43408035719): **Success**. Frontend build, backend tests/lint and data pipeline tests/lint all passed. The backend test log reported 89 passed and 6 skipped because SQL Server tests are opt-in in the standard workflow.

This result applies only to the disposable GitHub Actions test database. It does not prove that `USER_FAVORITES` exists in the user's local/shared/production database. Apply the migration separately only after confirming the intended target, backup/recovery plan, and a dedicated `_test` rehearsal.
