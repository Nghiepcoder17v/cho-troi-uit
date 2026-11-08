from fastapi import FastAPI

app = FastAPI(
    title="Chợ Trời UIT API",
    description="Backend API cho hệ thống giao dịch nội bộ sinh viên UIT",
    version="1.0.0"
)

# Endpoint kiểm tra trạng thái hệ thống
@app.get("/")
def health_check():
    return {
        "status": "success",
        "message": "UIT Exchange API is running perfectly!",
        "version": "1.0.0"
    }

# Endpoint thử nghiệm dựa trên API Contract
@app.get("/api/products")
def get_mock_products():
    return {
        "status": "success",
        "data": [
            {
                "product_id": 15,
                "title": "Bàn phím cơ ATK V75X",
                "price": 1200000.00,
                "condition": "Like New"
            }
        ]
    }