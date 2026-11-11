# CI và kiểm tra chất lượng

Workflow [CI](../.github/workflows/ci.yml) chạy khi mở/cập nhật Pull Request, khi có push lên `main`, hoặc được kích hoạt thủ công. Các job độc lập giúp thấy rõ lỗi thuộc backend, data pipeline hay frontend.

## Các job

| Job | Kiểm tra |
| --- | --- |
| Backend | Ruff lint và `pytest`; dùng SQLite in-memory cho test thường |
| Data pipeline | Ruff lint và toàn bộ `pytest` của pipeline |
| Frontend | `npm ci` theo lockfile và `npm run build` (TypeScript + Vite) |

Ruff dùng Python 3.12 và chỉ bật nhóm lỗi cơ bản về cú pháp/import (`E4`, `E7`, `E9`, `F`) để có baseline dễ duy trì. Bản Ruff được ghim trong requirements-dev của từng phần Python.

SQL Server integration tests không tự chạy trong CI thông thường. Chúng yêu cầu SQL Server riêng và database kiểm thử có tên kết thúc bằng `_test`; bảo vệ này được mô tả tại [SQL Server integration testing](SQLSERVER_INTEGRATION_TESTING.md). Khi môi trường CI có database chuyên dụng, có thể bổ sung job riêng với secret và dịch vụ phù hợp mà không bỏ qua kiểm tra tên database.

## Quy tắc Pull Request

Chờ cả ba job thành công trước khi merge. Workflow chỉ cấp quyền đọc repository, không chứa credential và không thực hiện deploy. Việc merge vẫn theo quy trình duyệt của chủ dự án.
