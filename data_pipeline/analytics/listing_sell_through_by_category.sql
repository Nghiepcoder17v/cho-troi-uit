-- Chụp trạng thái tin hiện hành theo danh mục và tỷ lệ tin đã bán hoàn tất.
-- Tỷ lệ sell-through = số tin có giao dịch Completed / tổng số tin hiện hành của danh mục.
WITH current_products AS (
    SELECT product_id, category_id, category_name, current_status, list_price
    FROM dim_product
    WHERE is_current = 1
), completed_sales AS (
    SELECT p.product_id,
           COUNT(DISTINCT f.transaction_id) AS completed_sales,
           SUM(f.amount) AS completed_revenue
    FROM fact_transactions f
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE f.is_completed = 1
    GROUP BY p.product_id
)
SELECT p.category_id,
       p.category_name,
       COUNT(*) AS total_listings,
       SUM(CASE WHEN p.current_status = 'Available' THEN 1 ELSE 0 END) AS available_listings,
       SUM(CASE WHEN p.current_status = 'Reserved' THEN 1 ELSE 0 END) AS reserved_listings,
       SUM(CASE WHEN p.current_status = 'Sold' THEN 1 ELSE 0 END) AS sold_listings,
       SUM(CASE WHEN p.current_status = 'Hidden' THEN 1 ELSE 0 END) AS hidden_listings,
       SUM(COALESCE(s.completed_sales, 0)) AS completed_sales,
       SUM(COALESCE(s.completed_revenue, 0)) AS completed_revenue,
       ROUND(
           100.0 * SUM(CASE WHEN COALESCE(s.completed_sales, 0) > 0 THEN 1 ELSE 0 END)
           / NULLIF(COUNT(*), 0),
           2
       ) AS sell_through_pct,
       ROUND(AVG(CASE WHEN p.current_status = 'Available' THEN p.list_price END), 2)
           AS avg_available_list_price
FROM current_products p
LEFT JOIN completed_sales s ON s.product_id = p.product_id
GROUP BY p.category_id, p.category_name
ORDER BY sell_through_pct DESC, p.category_name;
