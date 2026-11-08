# backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import engine, get_db

# Yêu cầu SQLAlchemy tạo bảng nếu chưa có
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Chợ Trời UIT API",
    description="Backend API cho hệ thống giao dịch nội bộ sinh viên UIT",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {"status": "success", "message": "SQL Server is connected!"}

@app.get("/api/products")
def get_mock_products():
    return {
        "status": "success",
        "data": [{"product_id": 15, "title": "Bàn phím cơ ATK V75X", "price": 1200000.00}]
    }

# ----------------------------------------------------
# API MỚI: TẠO NGƯỜI DÙNG (POST)
# ----------------------------------------------------
@app.post("/api/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra đuôi email (Bảo vệ lớp 1 ở Backend)
    if not user.email.endswith("@gm.uit.edu.vn"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận email sinh viên UIT (@gm.uit.edu.vn)")

    # 2. Kiểm tra xem MSSV đã tồn tại trong DB chưa
    db_user = db.query(models.User).filter(models.User.student_id == user.student_id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Mã số sinh viên này đã tồn tại trong hệ thống")

    # 3. Đưa dữ liệu vào Database
    new_user = models.User(
        student_id=user.student_id,
        email=user.email,
        full_name=user.full_name,
        major=user.major
    )
    db.add(new_user)
    db.commit()          # Lưu thay đổi (Tương đương lệnh COMMIT trong T-SQL)
    db.refresh(new_user) # Lấy lại data mới nhất (để biết user_id vừa tự tăng là bao nhiêu)

    return new_user