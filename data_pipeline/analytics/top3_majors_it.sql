-- Câu hỏi: Top 3 ngành học mua thiết bị IT nhiều nhất?
-- Định nghĩa "thiết bị IT" = hai danh mục cat_it_1 và cat_it_2 (khai báo trong run_analytics.py); chỉ tính giao dịch đã hoàn tất.
-- RANK() cho phép đồng hạng (có thể trả về nhiều hơn 3 dòng nếu hoà).
WITH purchases AS (
    SELECT u.major,
           COUNT(*)      AS purchases,
           SUM(f.amount) AS total_spent
    FROM fact_transactions f
    JOIN dim_user    u ON u.user_key    = f.buyer_user_key
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE f.is_completed = 1
      AND p.category_name IN (:cat_it_1, :cat_it_2)
    GROUP BY u.major
),
ranked AS (
    SELECT major, purchases, total_spent,
           RANK() OVER (ORDER BY purchases DESC)                    AS rnk,
           ROUND(100.0 * purchases / SUM(purchases) OVER (), 2)     AS pct_of_it_purchases
    FROM purchases
)
SELECT rnk, major, purchases, total_spent, pct_of_it_purchases
FROM ranked
WHERE rnk <= 3
ORDER BY rnk, major;
