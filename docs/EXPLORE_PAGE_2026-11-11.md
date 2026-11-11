# FE-2 — Trang Explore riêng

## Mục tiêu và phạm vi

Tách landing page khỏi luồng khám phá sản phẩm và thêm trang Explore có điều hướng riêng. Explore dùng API hiện tại cho tìm kiếm từ khóa, danh mục và phân trang; không hiển thị filter giá, tình trạng hoặc sắp xếp khi backend chưa hỗ trợ.

## Thay đổi

- `frontend/src/pages/MarketPage.tsx`: giữ vai trò landing, chuyển tìm kiếm/danh mục sang Explore.
- `frontend/src/pages/ExplorePage.tsx`: thêm search, danh mục đang chọn, số kết quả, loading, empty state, xóa bộ lọc, product grid và pagination.
- `frontend/src/components/AppShell.tsx`: thêm mục điều hướng Trang chủ và Khám phá.
- `frontend/src/App.tsx`: nối trang với `GET /api/products` qua các tham số `q`, `category_id`, `page`; trạng thái trang hồ sơ công khai giữ đúng trang quay lại.
- `frontend/src/styles.css`: bố cục responsive cho tiêu đề, bộ lọc danh mục và kết quả.

## Hành vi và giới hạn

- Chỉ tìm kiếm khi nhấn nút hoặc Enter; thay đổi từ khóa chưa gửi không tự gọi API.
- Danh mục, từ khóa và trang được gửi lên server; không lọc trên tập sản phẩm đã phân trang.
- Filter theo tình trạng, khoảng giá và sort chờ DB-5/API tương ứng.
- Lỗi tải được báo bằng toast lỗi dùng chung của ứng dụng. Màn hình Explore có trạng thái tải và không có kết quả.

## Kiểm tra

- `frontend/npm.cmd run build` — đạt (`tsc -b` và Vite production build).
- Chưa chạy browser check hoặc backend integration test trong bước FE-2.

## Git

- Branch: `feat/explore-page`
- Chưa tạo commit hoặc PR trong báo cáo này.
