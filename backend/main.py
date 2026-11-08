import math
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

import models
import schemas
from database import get_db
from security import create_access_token, get_current_user, hash_password, verify_password

# Lưu ý: backend KHÔNG tạo bảng. Schema nằm ở database_scripts/01_init_schema.sql

app = FastAPI(
    title="Chợ Trời UIT API",
    description="Backend API cho hệ thống giao dịch nội bộ sinh viên UIT",
    version="1.1.0",
)


@app.get("/")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Không kết nối được database")
    return {"status": "success", "message": "API và database đang hoạt động"}


# ==========================================================================
# 1. XÁC THỰC
# ==========================================================================
@app.post("/api/auth/register", response_model=schemas.UserEnvelope, status_code=201)
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
    exists = db.scalar(
        select(models.User.user_id).where(
            (models.User.email == body.email) | (models.User.student_id == body.student_id)
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="Email hoặc MSSV đã được đăng ký")

    user = models.User(
        student_id=body.student_id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        major=body.major,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # 2 request đăng ký trùng nhau chạy song song
        db.rollback()
        raise HTTPException(status_code=409, detail="Email hoặc MSSV đã được đăng ký")
    db.refresh(user)
    return {"status": "success", "message": "Đăng ký thành công", "data": user}


@app.post("/api/auth/login", response_model=schemas.TokenEnvelope)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == body.email))
    # Cùng một thông báo cho "sai email" và "sai mật khẩu" để không lộ email nào đã đăng ký
    if not verify_password(body.password, user.password_hash if user else None):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    return {
        "status": "success",
        "data": {"token": create_access_token(user.user_id), "user_id": user.user_id, "major": user.major},
    }


@app.get("/api/users/me", response_model=schemas.UserEnvelope)
def read_me(current_user: models.User = Depends(get_current_user)):
    return {"status": "success", "data": current_user}


# ==========================================================================
# 2. DANH MỤC & SẢN PHẨM
# ==========================================================================
@app.get("/api/categories", response_model=schemas.CategoryListEnvelope)
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Category).order_by(models.Category.category_id)).all()
    return {"status": "success", "data": rows}


@app.get("/api/products", response_model=schemas.ProductListEnvelope)
def list_products(
    category_id: Optional[int] = None,
    status: schemas.ProductStatus = "Available",
    q: Optional[str] = Query(None, max_length=100, description="Tìm theo tiêu đề"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if status == "Hidden":  # tin đã ẩn không công khai
        raise HTTPException(status_code=400, detail="Không thể liệt kê sản phẩm đã ẩn")

    conditions = [models.Product.status == status]
    if category_id is not None:
        conditions.append(models.Product.category_id == category_id)
    if q:
        conditions.append(models.Product.title.contains(q.strip(), autoescape=True))

    total = db.scalar(select(func.count()).select_from(models.Product).where(*conditions)) or 0
    rows = db.scalars(
        select(models.Product)
        .options(joinedload(models.Product.seller))
        .where(*conditions)
        .order_by(models.Product.created_at.desc(), models.Product.product_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "status": "success",
        "data": rows,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": math.ceil(total / page_size),
        },
    }


@app.get("/api/products/{product_id}", response_model=schemas.ProductEnvelope)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.scalar(
        select(models.Product)
        .options(joinedload(models.Product.seller))
        .where(models.Product.product_id == product_id)
    )
    if product is None or product.status == "Hidden":
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    return {"status": "success", "data": product}


@app.post("/api/products", response_model=schemas.ProductCreatedEnvelope, status_code=201)
def create_product(
    body: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if db.get(models.Category, body.category_id) is None:
        raise HTTPException(status_code=404, detail="Danh mục không tồn tại")

    product = models.Product(
        seller_id=current_user.user_id,  # lấy từ token, không tin client
        category_id=body.category_id,
        title=body.title,
        description=body.description,
        price=body.price,
        condition=body.condition,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {
        "status": "success",
        "message": "Product listed successfully",
        "data": {"product_id": product.product_id},
    }


# ==========================================================================
# 3. GIAO DỊCH (bảng Fact cho Data Pipeline)
# ==========================================================================
@app.post("/api/transactions", response_model=schemas.TransactionEnvelope, status_code=201)
def create_transaction(
    body: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    product = db.get(models.Product, body.product_id)
    if product is None or product.status == "Hidden":
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if product.seller_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Bạn không thể mua sản phẩm của chính mình")
    if body.amount > product.price:
        raise HTTPException(status_code=400, detail="Giá chốt không được cao hơn giá niêm yết")

    # "Giữ chỗ" nguyên tử: chỉ MỘT request đổi được Available -> Sold.
    # (Đọc status rồi mới ghi sẽ cho 2 người mua cùng lúc đều thành công.)
    # synchronize_session=False: tránh OUTPUT/RETURNING (SQL Server không cho kèm trigger).
    claimed = db.execute(
        update(models.Product)
        .where(models.Product.product_id == body.product_id, models.Product.status == "Available")
        .values(status="Sold", updated_at=models.utcnow()),
        execution_options={"synchronize_session": False},
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sản phẩm này đã được bán")

    transaction = models.Transaction(
        product_id=body.product_id,
        buyer_id=current_user.user_id,
        amount=body.amount,
        status="Completed",
    )
    db.add(transaction)
    try:
        db.commit()  # UPDATE product + INSERT transaction trong cùng một commit
    except IntegrityError:  # filtered unique index UX_Transactions_ActiveProduct
        db.rollback()
        raise HTTPException(status_code=409, detail="Sản phẩm này đã được bán")
    db.refresh(transaction)
    return {"status": "success", "message": "Đặt mua thành công", "data": transaction}
