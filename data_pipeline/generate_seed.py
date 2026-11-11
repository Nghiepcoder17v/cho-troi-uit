"""Sinh dữ liệu giả NHẤT QUÁN cho OLTP database (SQL Server) của Chợ Trời UIT.

Các quy tắc nhất quán (được kiểm tra tự động bởi validate_seed.py):
  * sản phẩm được đăng SAU khi người bán đăng ký; giao dịch xảy ra SAU khi sản phẩm được đăng
    và SAU khi người mua đăng ký; người mua != người bán
  * sản phẩm 'Sold'  <=> có đúng 1 giao dịch 'Completed'
  * sản phẩm khác 'Sold' không có giao dịch 'Completed'; chỉ có thể có giao dịch 'Cancelled'
  * giá chốt <= giá niêm yết; mọi thời điểm <= ngày kết thúc (--end-date)
  * ID tăng dần theo thời gian (như hệ thống thật), updated_at phản ánh lần thay đổi cuối
Có tính mùa vụ (đầu/cuối học kỳ đăng nhiều, giáo trình bán nhanh đầu kỳ) để các câu
phân tích như "tháng nào sách cũ cao điểm?" có kết quả có ý nghĩa.

Chạy (từ thư mục gốc repo, đã có .env với DATABASE_URL):
    python data_pipeline/generate_seed.py --reset
    python data_pipeline/generate_seed.py --users 500 --products 2500 --transactions 1000 --seed 7 --reset
"""
from __future__ import annotations

import argparse
import bisect
import os
import random
import sys
from datetime import date, datetime, timedelta

import bcrypt
import sqlalchemy as sa
from dotenv import load_dotenv

DEMO_PASSWORD = "Password123!"  # mật khẩu chung của mọi tài khoản giả (chỉ dùng khi dev)
COMPLETED_SHARE = 0.70          # tỉ lệ giao dịch Completed trong tổng số giao dịch
HIDDEN_SHARE = 0.08             # tỉ lệ sản phẩm (không bán) bị ẩn

CATEGORY_NAMES = ["Giáo trình", "Linh kiện IT", "Bàn phím & Chuột", "Phương tiện", "Khác"]
BOOKS = "Giáo trình"

# ------------------------------------------------------------------ bảng (Core, không phụ thuộc backend)
md = sa.MetaData()
categories_t = sa.Table(
    "categories", md,
    sa.Column("category_id", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("category_name", sa.Unicode(50)),
)
users_t = sa.Table(
    "users", md,
    sa.Column("user_id", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("student_id", sa.String(10)), sa.Column("email", sa.String(100)),
    sa.Column("password_hash", sa.String(100)), sa.Column("full_name", sa.Unicode(100)),
    sa.Column("major", sa.Unicode(50)),
    sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
)
products_t = sa.Table(
    "products", md,
    sa.Column("product_id", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("seller_id", sa.Integer), sa.Column("category_id", sa.Integer),
    sa.Column("title", sa.Unicode(200)), sa.Column("description", sa.UnicodeText),
    sa.Column("price", sa.Numeric(10, 2)), sa.Column("condition", sa.String(20)),
    sa.Column("status", sa.String(20)),
    sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
)
transactions_t = sa.Table(
    "transactions", md,
    sa.Column("transaction_id", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("product_id", sa.Integer), sa.Column("buyer_id", sa.Integer),
    sa.Column("amount", sa.Numeric(10, 2)), sa.Column("status", sa.String(20)),
    sa.Column("transaction_date", sa.DateTime), sa.Column("updated_at", sa.DateTime),
)

# ------------------------------------------------------------------ từ điển dữ liệu
MAJORS = ["Khoa học máy tính", "Kỹ thuật phần mềm", "Hệ thống thông tin", "An toàn thông tin",
          "Mạng máy tính", "Khoa học dữ liệu", "Trí tuệ nhân tạo", "Kỹ thuật máy tính",
          "Thương mại điện tử", "Công nghệ thông tin"]
MAJOR_WEIGHTS = [16, 18, 14, 11, 7, 8, 9, 6, 4, 7]

SURNAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Huỳnh", "Hoàng", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
SURNAME_WEIGHTS = [38, 11, 9, 7, 5, 5, 4, 4, 4, 3, 3, 2, 2, 1, 1, 1]
MALE_MID, FEMALE_MID = ["Văn", "Minh", "Quốc", "Đức", "Hoàng", "Gia", "Anh", "Hữu", "Thành"], ["Thị", "Ngọc", "Thanh", "Khánh", "Phương", "Mỹ", "Bảo"]
MALE_FIRST = ["Anh", "Bảo", "Dũng", "Hùng", "Khoa", "Long", "Nam", "Phúc", "Quân", "Tuấn", "Hiếu", "Nghĩa", "Thành", "Trung", "Khang", "Huy", "Đạt", "Kiệt"]
FEMALE_FIRST = ["Anh", "Châu", "Hà", "Hằng", "Lan", "Linh", "Mai", "My", "Ngân", "Nhi", "Phương", "Quyên", "Thảo", "Trang", "Vy", "Yến", "Trâm", "Uyên"]

BOOK_SUBJECTS = ["Cấu trúc dữ liệu và giải thuật", "Nhập môn lập trình", "Kỹ thuật lập trình", "Lập trình hướng đối tượng",
                 "Hệ điều hành", "Mạng máy tính", "Cơ sở dữ liệu", "Kiến trúc máy tính", "Giải tích", "Đại số tuyến tính",
                 "Xác suất thống kê", "Toán rời rạc", "Nhập môn công nghệ phần mềm", "Phân tích thiết kế hệ thống",
                 "Trí tuệ nhân tạo", "Học máy", "An toàn mạng", "Vật lý đại cương", "Triết học Mác-Lênin", "Tiếng Anh chuyên ngành"]
BOOK_SUFFIX = ["", "", "", " - còn mới", " (có ghi chú)", " kèm đề cương ôn thi", " (bản in 2023)"]

# (tên, giá thấp, giá cao) tính cho hàng ở tình trạng 'Like New'; tình trạng khác được nhân hệ số
ITEMS = {
    "Linh kiện IT": [("RAM laptop DDR4 8GB", 250_000, 450_000), ("RAM laptop DDR4 16GB", 450_000, 800_000),
                     ("SSD NVMe 256GB", 300_000, 500_000), ("SSD NVMe 512GB", 500_000, 900_000),
                     ("Ổ cứng HDD 1TB", 250_000, 450_000), ("Màn hình Dell 24 inch", 1_200_000, 2_000_000),
                     ("Màn hình LG 22 inch", 800_000, 1_300_000), ("Card đồ họa GTX 1650", 1_800_000, 2_800_000),
                     ("Raspberry Pi 4", 900_000, 1_400_000), ("Laptop Dell Latitude cũ", 3_000_000, 6_000_000)],
    "Bàn phím & Chuột": [("Chuột Logitech G102", 150_000, 280_000), ("Chuột Logitech M331", 120_000, 220_000),
                         ("Chuột Logitech MX Master 3", 900_000, 1_500_000), ("Bàn phím cơ Keychron K2", 800_000, 1_400_000),
                         ("Bàn phím cơ AKKO 3068", 600_000, 1_100_000), ("Bàn phím cơ iKBC CD87", 700_000, 1_200_000),
                         ("Bàn phím Dareu EK87", 350_000, 600_000), ("Chuột Razer DeathAdder", 400_000, 800_000)],
    "Phương tiện": [("Xe đạp Giant", 1_500_000, 3_500_000), ("Xe đạp gấp", 1_000_000, 2_500_000),
                    ("Xe máy Honda Wave Alpha", 8_000_000, 14_000_000), ("Xe máy Honda Vision", 15_000_000, 25_000_000),
                    ("Mũ bảo hiểm fullface", 150_000, 450_000)],
    "Khác": [("Quạt cây", 150_000, 350_000), ("Đèn học LED", 80_000, 200_000), ("Bàn gấp học bài", 100_000, 250_000),
             ("Balo laptop", 150_000, 400_000), ("Ổ cắm điện đa năng", 40_000, 120_000), ("Nồi cơm điện mini", 150_000, 350_000),
             ("Ấm đun siêu tốc", 80_000, 200_000), ("Kệ sách mini", 100_000, 300_000)],
}
CONDITIONS = ["Brand New", "Like New", "Good", "Fair"]
CONDITION_WEIGHTS = [10, 35, 40, 15]
CONDITION_FACTOR = {"Brand New": 1.15, "Like New": 1.0, "Good": 0.8, "Fair": 0.6}
DESCRIPTIONS = ["Cần pass nhanh", "Dùng ít, còn bảo hành", "Pass lại do không còn dùng", "Ai cần ib mình, giao dịch tại trường",
                "Còn rất mới, đầy đủ phụ kiện", "Có thể thương lượng nhẹ", "Giao dịch trực tiếp ở UIT", None]

# Hệ số mùa vụ theo tháng (đăng bán): nhiều vào cuối kỳ/đầu kỳ
MONTH_WEIGHT = {1: 1.2, 2: 1.4, 3: 1.0, 4: 0.8, 5: 1.2, 6: 1.3, 7: 0.8, 8: 1.3, 9: 1.6, 10: 1.0, 11: 0.9, 12: 1.0}
BOOK_BOOST_MONTHS = {2, 3, 9, 10}  # đầu học kỳ: giáo trình được đăng/bán nhiều hơn
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 1, 2, 3, 4, 4, 4, 5, 5, 5, 5, 5, 5, 6, 7, 9, 10, 10, 7, 3]
MEAN_DAYS_TO_SELL = {"Giáo trình": 6, "Linh kiện IT": 10, "Bàn phím & Chuột": 9, "Phương tiện": 25, "Khác": 12}


# ------------------------------------------------------------------ helpers
def rand_time(rng: random.Random, day: date) -> datetime:
    hour = rng.choices(range(24), HOUR_WEIGHTS)[0]
    return datetime(day.year, day.month, day.day, hour, rng.randrange(60), rng.randrange(60))


def day_weights(days: list[date], boost_books: bool) -> list[float]:
    return [MONTH_WEIGHT[d.month] * (1.8 if boost_books and d.month in BOOK_BOOST_MONTHS else 1.0) for d in days]


def make_name(rng: random.Random) -> str:
    surname = rng.choices(SURNAMES, SURNAME_WEIGHTS)[0]
    if rng.random() < 0.5:
        return f"{surname} {rng.choice(MALE_MID)} {rng.choice(MALE_FIRST)}"
    return f"{surname} {rng.choice(FEMALE_MID)} {rng.choice(FEMALE_FIRST)}"


def make_student_ids(rng: random.Random, n: int) -> list[str]:
    ids: set[str] = set()
    while len(ids) < n:
        ids.add(f"{rng.choice([21, 22, 23, 24, 25])}52{rng.randrange(10_000):04d}")
    ordered = sorted(ids)  # set không có thứ tự ổn định giữa các lần chạy -> sắp xếp trước khi xáo trộn
    rng.shuffle(ordered)
    return ordered


def round_down_thousand(x: float, floor: int = 10_000) -> int:
    return max(floor, int(x // 1000 * 1000))


# ------------------------------------------------------------------ sinh dữ liệu
def build_dataset(n_users: int, n_products: int, n_tx: int, end: datetime, seed: int, password_hash: str, cat_ids: dict[str, int]):
    rng = random.Random(seed)
    n_completed = round(n_tx * COMPLETED_SHARE)
    n_cancelled = n_tx - n_completed
    if n_completed > n_products:
        sys.exit(f"Số giao dịch Completed ({n_completed}) vượt số sản phẩm ({n_products}); hãy tăng --products.")
    if n_users < 10:
        sys.exit("Cần ít nhất 10 người dùng.")

    start = end - timedelta(days=365)
    all_days = [(start + timedelta(days=i)).date() for i in range(366)]
    # ---- USERS: đăng ký trải từ 120 ngày trước start tới end; 3 người đầu chắc chắn có từ trước start
    user_days = [(start - timedelta(days=120) + timedelta(days=i)).date() for i in range(486)]
    user_w = [MONTH_WEIGHT[d.month] for d in user_days]
    user_times = sorted(rand_time(rng, d) for d in rng.choices(user_days, user_w, k=n_users))
    for i in range(3):
        user_times[i] = min(user_times[i], start - timedelta(days=30 - i))
    user_times.sort()
    user_times = [min(t, end) for t in user_times]
    sids = make_student_ids(rng, n_users)
    users = [
        {"user_id": i + 1, "student_id": sids[i], "email": f"{sids[i]}@gm.uit.edu.vn", "password_hash": password_hash,
         "full_name": make_name(rng), "major": rng.choices(MAJORS, MAJOR_WEIGHTS)[0],
         "created_at": user_times[i], "updated_at": user_times[i]}
        for i in range(n_users)
    ]

    # ---- PRODUCTS (tạo trước theo category, sắp xếp theo thời gian rồi mới gán id)
    cat_names = list(cat_ids)
    cat_w = [30, 20, 18, 7, 25]  # tương ứng thứ tự CATEGORY_NAMES
    draft = []
    for _ in range(n_products):
        cat = rng.choices(cat_names, cat_w)[0]
        day = rng.choices(all_days, day_weights(all_days, cat == BOOKS))[0]
        created = min(rand_time(rng, day), end)
        # người bán phải đã đăng ký trước thời điểm đăng bán
        eligible = bisect.bisect_right(user_times, created)
        seller = users[rng.randrange(max(eligible, 1))]
        cond = rng.choices(CONDITIONS, CONDITION_WEIGHTS)[0]
        if cat == BOOKS:
            title = f"Giáo trình {rng.choice(BOOK_SUBJECTS)}{rng.choice(BOOK_SUFFIX)}"
            price = round_down_thousand(rng.uniform(25_000, 120_000) * CONDITION_FACTOR[cond], 10_000)
        else:
            name, lo, hi = rng.choice(ITEMS.get(cat, ITEMS["Khác"]))
            title = name
            price = round_down_thousand(rng.uniform(lo, hi) * CONDITION_FACTOR[cond], 10_000)
        draft.append({"seller_id": seller["user_id"], "category": cat, "title": title, "price": price,
                      "condition": cond, "description": rng.choice(DESCRIPTIONS), "created_at": created})
    draft.sort(key=lambda p: p["created_at"])
    products = []
    for i, p in enumerate(draft, 1):
        products.append({"product_id": i, "seller_id": p["seller_id"], "category_id": cat_ids[p["category"]],
                         "title": p["title"], "description": p["description"], "price": p["price"],
                         "condition": p["condition"], "status": "Available",
                         "created_at": p["created_at"], "updated_at": p["created_at"], "_cat": p["category"]})

    def tx_time(prod) -> datetime:
        mean = MEAN_DAYS_TO_SELL[prod["_cat"]]
        if prod["_cat"] == BOOKS and prod["created_at"].month in BOOK_BOOST_MONTHS:
            mean *= 0.6  # đầu kỳ sách bán nhanh hơn
        t = prod["created_at"] + timedelta(seconds=max(3600, rng.expovariate(1 / (mean * 86400))))
        if t > end:  # không để giao dịch nằm ở tương lai
            t = prod["created_at"] + (end - prod["created_at"]) * rng.random()
        return t.replace(microsecond=0)

    def pick_buyer(seller_id: int, when: datetime) -> int:
        eligible = max(bisect.bisect_right(user_times, when), 3)
        while True:
            u = users[rng.randrange(eligible)]
            if u["user_id"] != seller_id:
                return u["user_id"]

    # ---- TRANSACTIONS
    sold_idx = set(rng.sample(range(n_products), n_completed))
    txs = []
    for idx in sorted(sold_idx):  # sorted: giữ thứ tự dùng rng ổn định
        p = products[idx]
        when = tx_time(p)
        amount = round_down_thousand(p["price"] * rng.uniform(0.8, 1.0), 1_000)
        txs.append({"product_id": p["product_id"], "buyer_id": pick_buyer(p["seller_id"], when),
                    "amount": min(amount, p["price"]), "status": "Completed", "transaction_date": when})
        p["status"], p["updated_at"] = "Sold", when
    unsold = [p for i, p in enumerate(products) if i not in sold_idx]
    if n_cancelled and not unsold:
        sys.exit("Không còn sản phẩm chưa bán để gắn giao dịch Cancelled.")
    for _ in range(n_cancelled):
        p = rng.choice(unsold)
        when = tx_time(p)
        amount = round_down_thousand(p["price"] * rng.uniform(0.7, 1.0), 1_000)
        txs.append({"product_id": p["product_id"], "buyer_id": pick_buyer(p["seller_id"], when),
                    "amount": min(amount, p["price"]), "status": "Cancelled", "transaction_date": when})
    for p in unsold:  # một phần sản phẩm chưa bán bị người bán ẩn
        if rng.random() < HIDDEN_SHARE:
            p["status"] = "Hidden"
            p["updated_at"] = p["created_at"] + (end - p["created_at"]) * rng.random()
            p["updated_at"] = p["updated_at"].replace(microsecond=0)
    txs.sort(key=lambda t: t["transaction_date"])
    for i, t in enumerate(txs, 1):
        t["transaction_id"], t["updated_at"] = i, t["transaction_date"]
    for p in products:
        p.pop("_cat")
    return users, products, txs


# ------------------------------------------------------------------ nạp vào DB
def chunks(rows, size=5000):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def load(engine, users, products, txs, reset: bool):
    is_mssql = engine.dialect.name == "mssql"
    with engine.begin() as conn:
        existing = sum(conn.scalar(sa.select(sa.func.count()).select_from(t)) for t in (transactions_t, products_t, users_t))
        if existing and not reset:
            sys.exit(f"Database đã có {existing} dòng. Thêm --reset để XOÁ users/products/transactions cũ rồi nạp lại.")
        if reset:
            for t in (transactions_t, products_t, users_t):
                conn.execute(sa.delete(t))
        for table, rows in ((users_t, users), (products_t, products), (transactions_t, txs)):
            if is_mssql:
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {table.name} ON")
            for part in chunks(rows):
                conn.execute(sa.insert(table), part)
            if is_mssql:
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {table.name} OFF")
            print(f"  + {len(rows):>6} dòng -> {table.name}")


def ensure_categories(engine) -> dict[str, int]:
    with engine.begin() as conn:
        rows = conn.execute(sa.select(categories_t.c.category_id, categories_t.c.category_name)).all()
        if not rows:
            for i, name in enumerate(CATEGORY_NAMES, 1):
                if engine.dialect.name == "mssql":
                    conn.exec_driver_sql("SET IDENTITY_INSERT categories ON")
                conn.execute(sa.insert(categories_t).values(category_id=i, category_name=name))
                if engine.dialect.name == "mssql":
                    conn.exec_driver_sql("SET IDENTITY_INSERT categories OFF")
            rows = conn.execute(sa.select(categories_t.c.category_id, categories_t.c.category_name)).all()
    mapping = {name: cid for cid, name in rows}
    missing = [n for n in CATEGORY_NAMES if n not in mapping]
    if missing:
        sys.exit(f"Bảng categories thiếu: {missing}. Chạy database_scripts/02_seed_reference_data.sql trước.")
    return {n: mapping[n] for n in CATEGORY_NAMES}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", type=int, default=10_000)
    ap.add_argument("--products", type=int, default=50_000)
    ap.add_argument("--transactions", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=42, help="seed ngẫu nhiên -> chạy lại ra đúng cùng dữ liệu")
    ap.add_argument("--end-date", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD, mặc định hôm nay")
    ap.add_argument("--reset", action="store_true", help="xoá users/products/transactions hiện có trước khi nạp")
    args = ap.parse_args()

    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("Thiếu DATABASE_URL (xem .env.example).")
    engine = sa.create_engine(url, fast_executemany=True) if url.startswith("mssql") else sa.create_engine(url)

    cat_ids = ensure_categories(engine)
    end = datetime.combine(args.end_date, datetime.min.time()) + timedelta(hours=23, minutes=59)
    print("Đang băm mật khẩu demo (1 lần, dùng chung)...")
    pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    print(f"Đang sinh dữ liệu (seed={args.seed}, kết thúc {args.end_date})...")
    users, products, txs = build_dataset(args.users, args.products, args.transactions, end, args.seed, pw_hash, cat_ids)
    print("Đang nạp vào database...")
    load(engine, users, products, txs, args.reset)
    print(f"Xong. Đăng nhập thử: {users[0]['email']} / {DEMO_PASSWORD}")
    print("Chạy tiếp: python data_pipeline/validate_seed.py")


if __name__ == "__main__":
    main()
