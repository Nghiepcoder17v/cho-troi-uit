# backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Chợ Trời UIT API",
    description="Backend API cho hệ thống giao dịch nội bộ sinh viên UIT",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {"status": "success", "message": "SQL Server is connected!"}

# ==========================================
# 1. API NGƯỜI DÙNG
# ==========================================
@app.post("/api/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if not user.email.endswith("@gm.uit.edu.vn"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận email sinh viên UIT")

    if db.query(models.User).filter(models.User.student_id == user.student_id).first():
        raise HTTPException(status_code=400, detail="MSSV đã tồn tại")

    new_user = models.User(
        student_id=user.student_id,
        email=user.email,
        full_name=user.full_name,
        major=user.major
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ==========================================
# 2. API SẢN PHẨM
# ==========================================
# Lấy danh sách sản phẩm từ DB
@app.get("/api/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return {"status": "success", "data": products}

# Đăng bán sản phẩm mới
@app.post("/api/products", response_model=schemas.ProductResponse)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    # Kiểm tra xem danh mục có tồn tại không
    category = db.query(models.Category).filter(models.Category.category_id == product.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Danh mục không tồn tại")

    # Giả lập người dùng ID 1 đang đăng nhập để đăng bán
    seller = db.query(models.User).filter(models.User.user_id == 1).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Không tìm thấy người bán ID 1. Hãy gọi API tạo User trước!")

    new_product = models.Product(
        seller_id=1, # Tạm gán cứng người bán là user_id 1
        category_id=product.category_id,
        title=product.title,
        description=product.description,
        price=product.price,
        condition=product.condition
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

# Nối tiếp vào dưới cùng của backend/main.py

# ==========================================
# 3. API GIAO DỊCH (FACT TABLE)
# ==========================================
@app.post("/api/transactions", response_model=schemas.TransactionResponse)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra xem sản phẩm có tồn tại và còn "Available" không?
    product = db.query(models.Product).filter(models.Product.product_id == transaction.product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    if product.status != "Available":
        raise HTTPException(status_code=400, detail="Sản phẩm này đã được bán hoặc đang bị ẩn")

    # 2. Ghi nhận giao dịch (Tạm gán cứng buyer_id = 1)
    new_transaction = models.Transaction(
        product_id=transaction.product_id,
        buyer_id=1,
        amount=transaction.amount,
        status="Completed"
    )
    db.add(new_transaction)

    # 3. Cập nhật trạng thái sản phẩm thành "Sold"
    product.status = "Sold"

    # 4. Lưu đồng thời cả 2 thao tác vào SQL Server (Transaction Commit)
    db.commit()
    db.refresh(new_transaction)

    return new_transaction