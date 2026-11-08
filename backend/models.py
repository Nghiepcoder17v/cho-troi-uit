# backend/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(10), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    major = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(50), unique=True, nullable=False)

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    condition = Column(String(20), nullable=False)
    status = Column(String(20), default="Available")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Thiết lập mối quan hệ ORM
    seller = relationship("User")
    category = relationship("Category")

    # Nối tiếp vào dưới cùng của backend/models.py

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="Pending")
    transaction_date = Column(DateTime, default=datetime.utcnow)

    # Thiết lập liên kết ORM để dễ dàng truy vấn lồng (subqueries) sau này
    product = relationship("Product")
    buyer = relationship("User")