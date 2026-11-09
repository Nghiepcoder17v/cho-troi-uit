-- Câu hỏi: Tháng nào giao dịch sách (giáo trình) cũ cao điểm nhất?
-- peak_rank = 1 là tháng cao điểm. Lưu ý: tháng đầu và tháng cuối của dữ liệu có thể chưa đủ ngày.
WITH monthly AS (
    SELECT d.year_month,
           COUNT(*)      AS completed_sales,
           SUM(f.amount) AS revenue
    FROM fact_transactions f
    JOIN dim_date    d ON d.date_key    = f.transaction_date_key
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE f.is_completed = 1
      AND p.category_name = :cat_books
    GROUP BY d.year_month
)
SELECT year_month,
       completed_sales,
       revenue,
       RANK() OVER (ORDER BY completed_sales DESC)                                    AS peak_rank,
       completed_sales - LAG(completed_sales) OVER (ORDER BY year_month)              AS change_vs_prev_month,
       ROUND(100.0 * (completed_sales - LAG(completed_sales) OVER (ORDER BY year_month))
             / NULLIF(LAG(completed_sales) OVER (ORDER BY year_month), 0), 1)         AS pct_change
FROM monthly
ORDER BY year_month;
