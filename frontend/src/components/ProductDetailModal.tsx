import { useEffect, useState } from "react";
import { getSellerReputation, getUserReviews } from "../api";
import type { Product, Review, SellerReputation } from "../types";
import { money } from "../utils/format";
import { ReviewList } from "./ReviewList";

type ProductDetailModalProps = {
  product: Product;
  onClose: () => void;
  onAdd: () => void;
  onViewSeller: () => void;
};

export function ProductDetailModal({ product, onClose, onAdd, onViewSeller }: ProductDetailModalProps) {
  const [reputation, setReputation] = useState<SellerReputation | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      getSellerReputation(product.seller.user_id),
      getUserReviews(product.seller.user_id),
    ]).then(([nextReputation, nextReviews]) => {
      if (!active) return;
      setReputation(nextReputation);
      setReviews(nextReviews);
    }).catch(() => {
      if (active) setReviews([]);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [product.seller.user_id]);

  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="detail-modal">
      <button className="close-button" onClick={onClose}>×</button>
      <div className={`detail-image image-${product.product_id % 4}`}>
        <span className="image-glyph">{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span>
      </div>
      <div className="detail-content">
        <p className="eyebrow">{product.condition} · Chi tiết sản phẩm</p>
        <h2>{product.title}</h2>
        <strong className="detail-price">{money.format(product.price)}</strong>
        <p className="detail-description">{product.description || "Người bán chưa thêm mô tả cho sản phẩm này."}</p>
        <div className="trust-card">
          <span className="trust-icon">✓</span>
          <div>
            <strong>Lịch sử giao dịch</strong>
            <small>{reputation ? reputation.completed_sales + " giao dịch hoàn tất" : "Đang tải số liệu giao dịch..."}</small>
          </div>
        </div>
        <button type="button" className="text-button seller-profile-link" onClick={onViewSeller}>Xem trang cá nhân người bán ↗</button>
        <section className="review-section">
          <div className="review-section-heading">
            <div>
              <strong>Uy tín người bán</strong>
              <small>{reputation?.review_count ?? 0} đánh giá đã xác thực</small>
            </div>
            <strong className="review-score">
              {reputation?.score == null ? "Chưa có điểm" : `${reputation.score.toFixed(1)}/5`}
            </strong>
          </div>
          {loading ? <p className="muted">Đang tải đánh giá...</p> : <ReviewList reviews={reviews} emptyText="Người bán chưa nhận được đánh giá nào." />}
        </section>
        <button className="dark-button submit-button" onClick={onAdd} disabled={product.status !== "Available"}>
          {product.status === "Available" ? "Thêm vào giỏ hàng ↗" : product.status === "Reserved" ? "Đang được giữ chỗ" : "Sản phẩm đã bán"}
        </button>
      </div>
    </section>
  </div>;
}
