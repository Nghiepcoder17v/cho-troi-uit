"""ORM models - phản chiếu đúng schema trong database_scripts/01_init_schema.sql.

Nguồn sự thật của schema là file SQL (đã có index, trigger, filtered unique index).
Backend KHÔNG tự tạo bảng; các CheckConstraint bên dưới chỉ để model khớp với DB
và để unit test (SQLite) kiểm tra được ràng buộc.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Unicode,
    UnicodeText,
)
from sqlalchemy.orm import relationship

from database import Base


def utcnow() -> datetime:
    """Giờ UTC, không kèm tzinfo (khớp DATETIME2 + SYSUTCDATETIME() trong SQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(Unicode(50), unique=True, nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email LIKE '%@gm.uit.edu.vn'", name="CHK_User_Email"),
    )

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(8), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    full_name = Column(Unicode(100), nullable=False)
    major = Column(Unicode(50))
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="CHK_Product_Price"),
        CheckConstraint(
            "condition IN ('Brand New', 'Like New', 'Good', 'Fair')", name="CHK_Product_Condition"
        ),
        CheckConstraint("status IN ('Available', 'Reserved', 'Sold', 'Hidden')", name="CHK_Product_Status"),
    )

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)
    title = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    condition = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="Available")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    seller = relationship("User")
    category = relationship("Category")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="CHK_Transaction_Amount"),
        CheckConstraint(
            "status IN ('Pending', 'Accepted', 'Completed', 'Cancelled')", name="CHK_Transaction_Status"
        ),
    )

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="Pending")
    transaction_date = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    buyer_confirmed_at = Column(DateTime, nullable=True)
    seller_confirmed_at = Column(DateTime, nullable=True)

    product = relationship("Product")
    buyer = relationship("User")



class Review(Base):
    """Đánh giá hai chiều giữa buyer và seller sau một giao dịch hoàn tất."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id", "reviewer_id", name="UQ_Reviews_Transaction_Reviewer"
        ),
        CheckConstraint("rating >= 1 AND rating <= 5", name="CHK_Review_Rating"),
    )

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(
        Integer, ForeignKey("transactions.transaction_id"), nullable=False
    )
    reviewer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    reviewee_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Unicode(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    transaction = relationship("Transaction")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewee = relationship("User", foreign_keys=[reviewee_id])
