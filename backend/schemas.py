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