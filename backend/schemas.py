import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Condition = Literal["Brand New", "Like New", "Good", "Fair"]
ProductStatus = Literal["Available", "Reserved", "Sold", "Hidden"]
ProductVisibility = Literal["Available", "Hidden"]

_EMAIL_RE = re.compile(r"^[a-z0-9._+-]+@gm\.uit\.edu\.vn$")
_STUDENT_ID_RE = re.compile(r"^\d{8}$")
MAX_PRICE = Decimal("99999999.99")  # khớp DECIMAL(10,2)


# ---------------------------------------------------------------- AUTH
class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email trường, VD: 25520001@gm.uit.edu.vn")
    student_id: str = Field(..., description="MSSV 8 chữ số, phải trùng phần trước @ của email")
    full_name: str = Field(..., min_length=2, max_length=100)
    major: Optional[str] = Field(None, max_length=50)
    password: str = Field(..., min_length=8, description="Tối thiểu 8 ký tự (tối đa 72 byte UTF-8)")

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Chỉ chấp nhận email sinh viên UIT (@gm.uit.edu.vn)")
        return v

    @field_validator("student_id")
    @classmethod
    def _student_id(cls, v: str) -> str:
        v = v.strip()
        if not _STUDENT_ID_RE.match(v):
            raise ValueError("MSSV phải gồm đúng 8 chữ số")
        return v

    @field_validator("full_name", "major")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:  # giới hạn của bcrypt
            raise ValueError("Mật khẩu tối đa 72 byte")
        return v

    @model_validator(mode="after")
    def _email_matches_student_id(self):
        if self.email.split("@")[0] != self.student_id:
            raise ValueError("MSSV phải trùng với phần trước @ của email")
        return self


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    student_id: str
    email: str
    full_name: str
    major: Optional[str] = None
    created_at: datetime


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str


class SellerReputationOut(BaseModel):
    user_id: int
    score: Optional[float] = None
    completed_sales: int
    total_sales: int
    label: str


class TokenOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user_id: int
    major: Optional[str] = None


# ---------------------------------------------------------------- CATEGORY
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str


# ---------------------------------------------------------------- PRODUCT
class ProductCreate(BaseModel):
    category_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0, le=MAX_PRICE, decimal_places=2)
    condition: Condition

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tiêu đề không được để trống")
        return v


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0, le=MAX_PRICE, decimal_places=2)
    condition: Optional[Condition] = None
    status: Optional[ProductVisibility] = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Tiêu đề không được để trống")
        return v


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    category_id: int
    title: str
    description: Optional[str] = None
    price: float
    condition: str
    status: str
    created_at: datetime
    seller: SellerOut


class Pagination(BaseModel):
    current_page: int
    page_size: int
    total_items: int
    total_pages: int


class ProductCreated(BaseModel):
    product_id: int


# ---------------------------------------------------------------- TRANSACTION
class TransactionCreate(BaseModel):
    product_id: int
    amount: Decimal = Field(..., ge=0, le=MAX_PRICE, decimal_places=2, description="Giá chốt (<= giá niêm yết)")


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    product_id: int
    amount: float
    status: str
    transaction_date: datetime
    buyer_confirmed_at: Optional[datetime] = None
    seller_confirmed_at: Optional[datetime] = None


class TransactionHistoryOut(TransactionOut):
    product_title: str
    buyer: SellerOut
    seller: SellerOut


# ---------------------------------------------------------------- ENVELOPES (theo API contract)
class UserEnvelope(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: UserOut


class TokenEnvelope(BaseModel):
    status: str = "success"
    data: TokenOut


class CategoryListEnvelope(BaseModel):
    status: str = "success"
    data: list[CategoryOut]


class ProductListEnvelope(BaseModel):
    status: str = "success"
    data: list[ProductOut]
    pagination: Pagination


class ProductEnvelope(BaseModel):
    status: str = "success"
    data: ProductOut


class ProductCreatedEnvelope(BaseModel):
    status: str = "success"
    message: str
    data: ProductCreated


class TransactionEnvelope(BaseModel):
    status: str = "success"
    message: str
    data: TransactionOut


class ProductHistoryListEnvelope(BaseModel):
    status: str = "success"
    data: list[ProductOut]
    pagination: Pagination


class TransactionHistoryListEnvelope(BaseModel):
    status: str = "success"
    data: list[TransactionHistoryOut]


class SellerReputationEnvelope(BaseModel):
    status: str = "success"
    data: SellerReputationOut
