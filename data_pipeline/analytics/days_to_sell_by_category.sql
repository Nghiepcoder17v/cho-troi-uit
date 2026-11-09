-- Câu hỏi: Danh mục nào bán nhanh nhất, và người mua trả giá thấp hơn niêm yết bao nhiêu?
SELECT p.category_name,
       COUNT(*)                                           AS completed_sales,
       ROUND(AVG(f.days_to_sell), 1)                      AS avg_days_to_sell,
       ROUND(AVG(f.discount_pct), 1)                      AS avg_discount_pct,
       RANK() OVER (ORDER BY AVG(f.days_to_sell))         AS fastest_rank
FROM fact_transactions f
JOIN dim_product p ON p.product_key = f.product_key
WHERE f.is_completed = 1
GROUP BY p.category_name
ORDER BY fastest_rank;
