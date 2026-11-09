-- Câu hỏi: 10 người bán có doanh thu cao nhất chiếm bao nhiêu % tổng doanh thu (phân tích Pareto)?
-- Dùng window function tích luỹ (running total) trên CTE.
WITH seller_revenue AS (
    SELECT s.user_key, s.full_name, s.major,
           COUNT(*)      AS sales,
           SUM(f.amount) AS revenue
    FROM fact_transactions f
    JOIN dim_user s ON s.user_key = f.seller_user_key
    WHERE f.is_completed = 1
    GROUP BY s.user_key, s.full_name, s.major
),
ranked AS (
    SELECT full_name, major, sales, revenue,
           ROW_NUMBER() OVER (ORDER BY revenue DESC, user_key) AS rn,
           SUM(revenue) OVER (ORDER BY revenue DESC, user_key
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_revenue,
           SUM(revenue) OVER ()                                 AS total_revenue
    FROM seller_revenue
)
SELECT rn, full_name, major, sales, revenue,
       ROUND(100.0 * running_revenue / total_revenue, 2) AS cumulative_pct_of_revenue
FROM ranked
WHERE rn <= 10
ORDER BY rn;
