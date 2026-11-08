import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker('vi_VN')

NUM_USERS = 50
NUM_PRODUCTS = 150
NUM_TRANSACTIONS = 80

def generate_sql():
    with open('seed_data.sql', 'w', encoding='utf-8') as f:
        f.write("-- ==========================================\n")
        f.write("-- MOCK DATA CHO CHỢ TRỜI UIT\n")
        f.write("-- ==========================================\n\n")

        # 1. CATEGORIES
        categories = ['Giáo trình', 'Linh kiện IT', 'Bàn phím & Chuột', 'Phương tiện', 'Khác']
        f.write("SET IDENTITY_INSERT CATEGORIES ON;\n")
        for i, cat in enumerate(categories, 1):
            f.write(f"INSERT INTO CATEGORIES (category_id, category_name) VALUES ({i}, N'{cat}');\n")
        f.write("SET IDENTITY_INSERT CATEGORIES OFF;\n\n")

        # 2. USERS
        f.write("SET IDENTITY_INSERT USERS ON;\n")
        majors = ['Hệ thống thông tin', 'Kỹ thuật phần mềm', 'Khoa học máy tính', 'An toàn thông tin', 'Mạng máy tính']
        for i in range(1, NUM_USERS + 1):
            # Giả lập MSSV khóa 2025 (2552xxxx)
            student_id = f"2552{random.randint(1000, 9999)}"
            email = f"{student_id}@gm.uit.edu.vn"
            full_name = fake.name()
            major = random.choice(majors)
            created_at = fake.date_time_between(start_date='-1y', end_date='now').strftime('%Y-%m-%d %H:%M:%S')

            f.write(f"INSERT INTO USERS (user_id, student_id, email, full_name, major, created_at) "
                    f"VALUES ({i}, '{student_id}', '{email}', N'{full_name}', N'{major}', '{created_at}');\n")
        f.write("SET IDENTITY_INSERT USERS OFF;\n\n")

        # 3. PRODUCTS
        f.write("SET IDENTITY_INSERT PRODUCTS ON;\n")
        conditions = ['Brand New', 'Like New', 'Good', 'Fair']
        statuses = ['Available', 'Sold', 'Hidden']
        for i in range(1, NUM_PRODUCTS + 1):
            seller_id = random.randint(1, NUM_USERS)
            category_id = random.randint(1, len(categories))

            # Tên sản phẩm giả lập cho sinh viên IT
            if category_id == 1: title = f"Giáo trình {fake.catch_phrase()}"
            elif category_id == 2: title = f"Màn hình cũ {fake.word().capitalize()}"
            elif category_id == 3: title = f"Bàn phím cơ {fake.word().capitalize()} Switch"
            else: title = fake.sentence(nb_words=4)

            price = round(random.uniform(50000, 2000000), -3) # Làm tròn tới nghìn đồng
            condition = random.choice(conditions)
            status = random.choice(statuses)
            created_at = fake.date_time_between(start_date='-6m', end_date='now').strftime('%Y-%m-%d %H:%M:%S')

            f.write(f"INSERT INTO PRODUCTS (product_id, seller_id, category_id, title, description, price, condition, status, created_at) "
                    f"VALUES ({i}, {seller_id}, {category_id}, N'{title}', N'Cần pass nhanh', {price}, '{condition}', '{status}', '{created_at}');\n")
        f.write("SET IDENTITY_INSERT PRODUCTS OFF;\n\n")

        # 4. TRANSACTIONS
        f.write("SET IDENTITY_INSERT TRANSACTIONS ON;\n")
        t_statuses = ['Pending', 'Completed', 'Cancelled']
        for i in range(1, NUM_TRANSACTIONS + 1):
            product_id = random.randint(1, NUM_PRODUCTS)
            # Đảm bảo người mua khác người bán
            buyer_id = random.randint(1, NUM_USERS)

            amount = round(random.uniform(40000, 2000000), -3)
            status = random.choice(t_statuses)
            t_date = fake.date_time_between(start_date='-3m', end_date='now').strftime('%Y-%m-%d %H:%M:%S')

            f.write(f"INSERT INTO TRANSACTIONS (transaction_id, product_id, buyer_id, amount, status, transaction_date) "
                    f"VALUES ({i}, {product_id}, {buyer_id}, {amount}, '{status}', '{t_date}');\n")
        f.write("SET IDENTITY_INSERT TRANSACTIONS OFF;\n")

if __name__ == "__main__":
    generate_sql()
    print("Đã tạo thành công file seed_data.sql!")