import math
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

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

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    if status != "Available":  # chỉ tin sẵn sàng mới được xuất hiện trong chợ công khai
        raise HTTPException(status_code=400, detail="Chợ công khai chỉ liệt kê sản phẩm đang Available")

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


@app.get("/api/products/mine", response_model=schemas.ProductHistoryListEnvelope)
def list_my_products(
    status: Optional[schemas.ProductStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conditions = [models.Product.seller_id == current_user.user_id]
    if status is not None:
        conditions.append(models.Product.status == status)
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


@app.get("/api/users/{user_id}/reviews", response_model=schemas.ReviewListEnvelope)
def list_user_reviews(user_id: int, db: Session = Depends(get_db)):
    if db.get(models.User, user_id) is None:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    rows = db.execute(
        select(models.Review, models.User, models.Product)
        .join(models.User, models.Review.reviewer_id == models.User.user_id)
        .join(
            models.Transaction,
            models.Review.transaction_id == models.Transaction.transaction_id,
        )
        .join(models.Product, models.Transaction.product_id == models.Product.product_id)
        .where(models.Review.reviewee_id == user_id)
        .order_by(models.Review.created_at.desc(), models.Review.review_id.desc())
    ).all()
    data = [
        {
            "review_id": review.review_id,
            "transaction_id": review.transaction_id,
            "reviewer_id": review.reviewer_id,
            "reviewee_id": review.reviewee_id,
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
            "reviewer": {
                "user_id": reviewer.user_id,
                "full_name": reviewer.full_name,
            },
            "product_title": product.title,
        }
        for review, reviewer, product in rows
    ]
    return {"status": "success", "data": data}


@app.get("/api/users/{user_id}/reputation", response_model=schemas.SellerReputationEnvelope)
def get_seller_reputation(user_id: int, db: Session = Depends(get_db)):
    if db.get(models.User, user_id) is None:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    total_sales = db.scalar(
        select(func.count(models.Transaction.transaction_id))
        .join(models.Product, models.Transaction.product_id == models.Product.product_id)
        .where(models.Product.seller_id == user_id)
    ) or 0
    completed_sales = db.scalar(
        select(func.count(models.Transaction.transaction_id))
        .join(models.Product, models.Transaction.product_id == models.Product.product_id)
        .where(
            models.Product.seller_id == user_id,
            models.Transaction.status == "Completed",
        )
    ) or 0
    review_count = db.scalar(
        select(func.count(models.Review.review_id)).where(
            models.Review.reviewee_id == user_id
        )
    ) or 0
    average_rating = db.scalar(
        select(func.avg(models.Review.rating)).where(
            models.Review.reviewee_id == user_id
        )
    )
    score = round(float(average_rating), 1) if average_rating is not None else None
    distribution = {str(rating): 0 for rating in range(1, 6)}
    for rating, count in db.execute(
        select(models.Review.rating, func.count(models.Review.review_id))
        .where(models.Review.reviewee_id == user_id)
        .group_by(models.Review.rating)
    ).all():
        distribution[str(rating)] = int(count)
    label = (
        "Chưa có đánh giá"
        if score is None
        else f"{score:.1f}/5 từ {review_count} đánh giá"
    )
    return {
        "status": "success",
        "data": {
            "user_id": user_id,
            "score": score,
            "review_count": review_count,
            "rating_distribution": distribution,
            "completed_sales": completed_sales,
            "total_sales": total_sales,
            "label": label,
        },
    }


@app.patch("/api/products/{product_id}", response_model=schemas.ProductEnvelope)
def update_product(
    product_id: int,
    body: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    product = db.scalar(
        select(models.Product)
        .options(joinedload(models.Product.seller))
        .where(
            models.Product.product_id == product_id,
            models.Product.seller_id == current_user.user_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if product.status in {"Reserved", "Sold"}:
        raise HTTPException(status_code=409, detail="Không thể chỉnh sửa sản phẩm đang được giữ chỗ hoặc đã bán")
    if body.category_id is not None and db.get(models.Category, body.category_id) is None:
        raise HTTPException(status_code=404, detail="Danh mục không tồn tại")

    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return {"status": "success", "data": product}


# ==========================================================================
# 3. GIAO DỊCH (quy trình yêu cầu mua và xác nhận hai bên)
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
    if product.status != "Available":
        raise HTTPException(status_code=409, detail="Sản phẩm đã được giữ chỗ hoặc không còn khả dụng")
    if body.amount > product.price:
        raise HTTPException(status_code=400, detail="Giá đề nghị không được cao hơn giá niêm yết")

    # Chỉ một request được phép giữ chỗ Available -> Reserved; so khớp cả giá hiện tại.
    claimed = db.execute(
        update(models.Product)
        .where(
            models.Product.product_id == body.product_id,
            models.Product.status == "Available",
            models.Product.price == product.price,
        )
        .values(status="Reserved", updated_at=models.utcnow()),
        execution_options={"synchronize_session": False},
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sản phẩm vừa thay đổi hoặc đã được người khác giữ chỗ")

    transaction = models.Transaction(
        product_id=body.product_id,
        buyer_id=current_user.user_id,
        amount=body.amount,
        status="Pending",
    )
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sản phẩm này đã có yêu cầu mua đang hoạt động")
    db.refresh(transaction)
    return {
        "status": "success",
        "message": "Đã gửi yêu cầu mua. Sản phẩm đang được giữ chỗ chờ người bán phản hồi.",
        "data": transaction,
    }


def _get_transaction_context(db: Session, transaction_id: int):
    row = db.execute(
        select(models.Transaction, models.Product)
        .join(models.Product, models.Transaction.product_id == models.Product.product_id)
        .where(models.Transaction.transaction_id == transaction_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Giao dịch không tồn tại")
    return row[0], row[1]


@app.post("/api/transactions/{transaction_id}/accept", response_model=schemas.TransactionEnvelope)
def accept_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    transaction, product = _get_transaction_context(db, transaction_id)
    if product.seller_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Chỉ người bán mới có thể chấp nhận yêu cầu")
    changed = db.execute(
        update(models.Transaction)
        .where(
            models.Transaction.transaction_id == transaction_id,
            models.Transaction.status == "Pending",
        )
        .values(status="Accepted", updated_at=models.utcnow()),
        execution_options={"synchronize_session": False},
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Yêu cầu không còn ở trạng thái chờ người bán")
    db.commit()
    db.refresh(transaction)
    return {"status": "success", "message": "Đã chấp nhận yêu cầu mua", "data": transaction}


@app.post("/api/transactions/{transaction_id}/reject", response_model=schemas.TransactionEnvelope)
def reject_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    transaction, product = _get_transaction_context(db, transaction_id)
    if product.seller_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Chỉ người bán mới có thể từ chối yêu cầu")
    changed = db.execute(
        update(models.Transaction)
        .where(
            models.Transaction.transaction_id == transaction_id,
            models.Transaction.status == "Pending",
        )
        .values(status="Cancelled", updated_at=models.utcnow()),
        execution_options={"synchronize_session": False},
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Chỉ có thể từ chối yêu cầu đang chờ")
    released = db.execute(
        update(models.Product)
        .where(
            models.Product.product_id == transaction.product_id,
            models.Product.status == "Reserved",
        )
        .values(status="Available", updated_at=models.utcnow()),
        execution_options={"synchronize_session": False},
    )
    if released.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Không thể giải phóng sản phẩm; trạng thái dữ liệu đã thay đổi")
    db.commit()
    db.refresh(transaction)
    return {"status": "success", "message": "Đã từ chối yêu cầu và mở bán lại sản phẩm", "data": transaction}


@app.post("/api/transactions/{transaction_id}/cancel", response_model=schemas.TransactionEnvelope)
def cancel_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    transaction, product = _get_transaction_context(db, transaction_id)
    is_buyer = transaction.buyer_id == current_user.user_id
    is_seller = product.seller_id == current_user.user_id
    if not (is_buyer or is_seller):
        raise HTTPException(status_code=403, detail="Bạn không tham gia giao dịch này")
    changed = db.execute(
        update(models.Transaction)
        .where(
            models.Transaction.transaction_id == transaction_id,
            models.Transaction.status.in_(("Pending", "Accepted")),
        )
        .values(
            status="Cancelled",
            buyer_confirmed_at=None,
            seller_confirmed_at=None,
            updated_at=models.utcnow(),
        ),
        execution_options={"synchronize_session": False},
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Giao dịch đã hoàn tất, đã hủy hoặc không thể hủy")
    released = db.execute(
        update(models.Product)
        .where(
            models.Product.product_id == transaction.product_id,
            models.Product.status == "Reserved",
        )
        .values(status="Available", updated_at=models.utcnow()),
        execution_options={"synchronize_session": False},
    )
    if released.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Không thể giải phóng sản phẩm; trạng thái dữ liệu đã thay đổi")
    db.commit()
    db.refresh(transaction)
    return {"status": "success", "message": "Đã hủy giao dịch và mở bán lại sản phẩm", "data": transaction}


@app.post("/api/transactions/{transaction_id}/confirm-completion", response_model=schemas.TransactionEnvelope)
def confirm_transaction_completion(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    transaction, product = _get_transaction_context(db, transaction_id)
    is_buyer = transaction.buyer_id == current_user.user_id
    is_seller = product.seller_id == current_user.user_id
    if not (is_buyer or is_seller):
        raise HTTPException(status_code=403, detail="Bạn không tham gia giao dịch này")
    if transaction.status != "Accepted":
        raise HTTPException(status_code=409, detail="Chỉ giao dịch đã được người bán chấp nhận mới có thể xác nhận")

    now = models.utcnow()
    if is_buyer:
        changed = db.execute(
            update(models.Transaction)
            .where(
                models.Transaction.transaction_id == transaction_id,
                models.Transaction.status == "Accepted",
                models.Transaction.buyer_confirmed_at.is_(None),
            )
            .values(
                buyer_confirmed_at=now,
                status=case(
                    (models.Transaction.seller_confirmed_at.is_not(None), "Completed"),
                    else_="Accepted",
                ),
                updated_at=now,
            ),
            execution_options={"synchronize_session": False},
        )
    else:
        changed = db.execute(
            update(models.Transaction)
            .where(
                models.Transaction.transaction_id == transaction_id,
                models.Transaction.status == "Accepted",
                models.Transaction.seller_confirmed_at.is_(None),
            )
            .values(
                seller_confirmed_at=now,
                status=case(
                    (models.Transaction.buyer_confirmed_at.is_not(None), "Completed"),
                    else_="Accepted",
                ),
                updated_at=now,
            ),
            execution_options={"synchronize_session": False},
        )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bạn đã xác nhận rồi hoặc giao dịch vừa thay đổi")

    current_status = db.scalar(
        select(models.Transaction.status).where(models.Transaction.transaction_id == transaction_id)
    )
    if current_status == "Completed":
        sold = db.execute(
            update(models.Product)
            .where(
                models.Product.product_id == transaction.product_id,
                models.Product.status == "Reserved",
            )
            .values(status="Sold", updated_at=models.utcnow()),
            execution_options={"synchronize_session": False},
        )
        if sold.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Không thể hoàn tất vì sản phẩm không còn ở trạng thái giữ chỗ")

    db.commit()
    db.refresh(transaction)
    message = (
        "Hai bên đã xác nhận. Giao dịch hoàn tất và sản phẩm được đánh dấu đã bán."
        if transaction.status == "Completed"
        else "Đã ghi nhận xác nhận của bạn. Giao dịch chờ bên còn lại xác nhận."
    )
    return {"status": "success", "message": message, "data": transaction}


@app.post(
    "/api/transactions/{transaction_id}/reviews",
    response_model=schemas.ReviewEnvelope,
    status_code=201,
)
def create_transaction_review(
    transaction_id: int,
    body: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    transaction, product = _get_transaction_context(db, transaction_id)
    is_buyer = transaction.buyer_id == current_user.user_id
    is_seller = product.seller_id == current_user.user_id
    if not (is_buyer or is_seller):
        raise HTTPException(status_code=403, detail="Bạn không tham gia giao dịch này")
    if transaction.status != "Completed":
        raise HTTPException(status_code=409, detail="Chỉ giao dịch Completed mới được đánh giá")

    reviewee_id = product.seller_id if is_buyer else transaction.buyer_id
    if reviewee_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Bạn không thể tự đánh giá chính mình")

    existing = db.scalar(
        select(models.Review.review_id).where(
            models.Review.transaction_id == transaction_id,
            models.Review.reviewer_id == current_user.user_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Bạn đã đánh giá giao dịch này. Hãy chỉnh sửa đánh giá hiện có.",
        )

    review = models.Review(
        transaction_id=transaction_id,
        reviewer_id=current_user.user_id,
        reviewee_id=reviewee_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bạn đã đánh giá giao dịch này")
    db.refresh(review)
    return {
        "status": "success",
        "message": "Đã gửi đánh giá.",
        "data": review,
    }


@app.patch("/api/reviews/{review_id}", response_model=schemas.ReviewEnvelope)
def update_review(
    review_id: int,
    body: schemas.ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    review = db.get(models.Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Đánh giá không tồn tại")
    if review.reviewer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bạn chỉ có thể chỉnh sửa đánh giá của chính mình")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    review.updated_at = models.utcnow()
    db.commit()
    db.refresh(review)
    return {
        "status": "success",
        "message": "Đã cập nhật đánh giá.",
        "data": review,
    }


def _transaction_history(
    db: Session,
    user_id: int,
    *,
    buyer: bool,
) -> list[dict]:
    buyer_user = aliased(models.User)
    seller_user = aliased(models.User)
    user_column = models.Transaction.buyer_id if buyer else models.Product.seller_id
    rows = db.execute(
        select(models.Transaction, models.Product, buyer_user, seller_user)
        .join(models.Product, models.Transaction.product_id == models.Product.product_id)
        .join(buyer_user, models.Transaction.buyer_id == buyer_user.user_id)
        .join(seller_user, models.Product.seller_id == seller_user.user_id)
        .where(user_column == user_id)
        .order_by(models.Transaction.transaction_date.desc(), models.Transaction.transaction_id.desc())
    ).all()
    transaction_ids = [transaction.transaction_id for transaction, *_ in rows]
    reviews = (
        db.scalars(
            select(models.Review).where(
                models.Review.reviewer_id == user_id,
                models.Review.transaction_id.in_(transaction_ids),
            )
        ).all()
        if transaction_ids
        else []
    )
    reviews_by_transaction = {review.transaction_id: review for review in reviews}

    history = []
    for transaction, product, buyer_user, seller_user in rows:
        own_review = reviews_by_transaction.get(transaction.transaction_id)
        history.append(
            {
                "transaction_id": transaction.transaction_id,
                "product_id": transaction.product_id,
                "amount": transaction.amount,
                "status": transaction.status,
                "transaction_date": transaction.transaction_date,
                "buyer_confirmed_at": transaction.buyer_confirmed_at,
                "seller_confirmed_at": transaction.seller_confirmed_at,
                "product_title": product.title,
                "buyer": {"user_id": buyer_user.user_id, "full_name": buyer_user.full_name},
                "seller": {"user_id": seller_user.user_id, "full_name": seller_user.full_name},
                "my_review": (
                    {
                        "review_id": own_review.review_id,
                        "rating": own_review.rating,
                        "comment": own_review.comment,
                        "created_at": own_review.created_at,
                        "updated_at": own_review.updated_at,
                    }
                    if own_review
                    else None
                ),
            }
        )
    return history


@app.get("/api/transactions/purchases", response_model=schemas.TransactionHistoryListEnvelope)
def list_purchases(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return {"status": "success", "data": _transaction_history(db, current_user.user_id, buyer=True)}


@app.get("/api/transactions/sales", response_model=schemas.TransactionHistoryListEnvelope)
def list_sales(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return {"status": "success", "data": _transaction_history(db, current_user.user_id, buyer=False)}
