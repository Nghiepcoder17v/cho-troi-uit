# backend/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Định dạng dữ liệu yêu cầu Frontend gửi lên
class UserCreate(BaseModel):
    student_id: str = Field(..., description="Mã số sinh viên (VD: 25520001)")
    email: str = Field(..., description="Email trường (@gm.uit.edu.vn)")
    full_name: str
    major: Optional[str] = None

# Định dạng dữ liệu Backend sẽ trả về sau khi lưu thành công
class UserResponse(BaseModel):
    user_id: int
    student_id: str
    email: str
    full_name: str
    major: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True # Bắt buộc để đọc được dữ liệu từ SQLAlchemy ORM

# ... (Giữ nguyên class UserCreate và UserResponse) ...

class ProductCreate(BaseModel):
    category_id: int
    title: str = Field(..., description="Tên sản phẩm")
    description: Optional[str] = None
    price: float = Field(..., ge=0, description="Giá sản phẩm (phải >= 0)")
    condition: str = Field(..., description="Tình trạng: Brand New, Like New, Good, Fair")

class ProductResponse(BaseModel):
    product_id: int
    seller_id: int
    category_id: int
    title: str
    price: float
    condition: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Nối tiếp vào dưới cùng của backend/schemas.py

class TransactionCreate(BaseModel):
    product_id: int
    amount: float = Field(..., ge=0, description="Giá chốt đơn (có thể mặc cả, phải >= 0)")

class TransactionResponse(BaseModel):
    transaction_id: int
    product_id: int
    buyer_id: int
    amount: float
    status: str
    transaction_date: datetime

    class Config:
        from_attributes = True