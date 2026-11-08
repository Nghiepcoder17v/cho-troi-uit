# Chợ Trời UIT (UIT Exchange)

Dự án cá nhân: Hệ thống mua bán trao đổi nội bộ sinh viên (C2C) kết hợp Data Pipeline phân tích hành vi.

## 📌 Tổng quan dự án
- **Mục tiêu**: Xây dựng một chợ điện tử mini, bảo mật cho sinh viên UIT mua bán đồ cũ, đồng thời tận dụng chính nguồn dữ liệu này để thực hành thiết kế Luồng dữ liệu (Data Pipeline) cho một Data Engineer.
- **Tính năng nổi bật**: Xác thực email trường, đăng tin, bộ lọc tìm kiếm và tự động hóa ETL dữ liệu giao dịch về kho phân tích.

## 📂 Cấu trúc thư mục
- `/backend`: Mã nguồn xử lý logic và API.
- `/database_scripts`: Các mã nguồn khởi tạo & tối ưu Database OLTP (SQL).
- `/data_pipeline`: Các script Python xử lý luồng trích xuất, làm sạch dữ liệu (ETL).
- `/docs`: Tài liệu chi tiết của dự án.