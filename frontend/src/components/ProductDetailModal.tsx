import { useEffect, useRef, useState } from "react";
import { getSellerReputation, getUserReviews } from "../api";
import { useDialogFocus } from "../hooks/useDialogFocus";
import { Skeleton, StatusBadge } from "./primitives";
import type { Product, Review, SellerReputation } from "../types";
import { money } from "../utils/format";
import { ReviewList } from "./ReviewList";
import { ProductMediaGallery } from "./ProductMediaGallery";

type ProductDetailModalProps = {
  product: Product;
  onClose: () => void;
  isFavorite: boolean;
  favoriteBusy: boolean;
  onToggleFavorite: () => void;
  onAdd: () => void;
  onViewSeller: () => void;
};

export function ProductDetailModal({
  product, isFavorite, favoriteBusy, onToggleFavorite, onClose, onAdd, onViewSeller,
}: ProductDetailModalProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const [reputation, setReputation] = useState<SellerReputation | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  useDialogFocus(dialogRef, onClose);

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
    <section ref={dialogRef} className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="product-detail-title" tabIndex={-1}>
      <button type="button" className="close-button" aria-label="Đóng chi tiết sản phẩm" onClick={onClose}>×</button>
      <div className={`detail-image image-${product.product_id % 4}`}>
        <ProductMediaGallery media={product.media} productId={product.product_id} productTitle={product.title} fallbackGlyph={["⌨", "◒", "▤", "✦"][product.product_id % 4]} mode="detail" />
      </div>
      <div className="detail-content">
        <p className="eyebrow">{product.condition} · Chi tiết sản phẩm</p>
        <StatusBadge tone={product.status === "Available" ? "success" : product.status === "Reserved" ? "warning" : product.status === "Sold" ? "info" : "neutral"}>
          {product.status === "Available" ? "Đang mở bán" : product.status === "Reserved" ? "Đang được giữ chỗ" : product.status === "Sold" ? "Đã bán" : "Tin đã ẩn"}
        </StatusBadge>
        <h2 id="product-detail-title">{product.title}</h2>
        <strong className="detail-price">{money.format(product.price)}</strong>
        <button
          type="button"
          className="favorite-detail-toggle"
          aria-pressed={isFavorite}
          disabled={favoriteBusy}
          onClick={onToggleFavorite}
        >{isFavorite ? "♥ Đã lưu" : "♡ Lưu sản phẩm"}</button>
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
          {loading ? <Skeleton label="Đang tải đánh giá của người bán" /> : <ReviewList reviews={reviews} emptyText="Người bán chưa nhận được đánh giá nào." />}
        </section>
        <button className="dark-button submit-button" onClick={onAdd} disabled={product.status !== "Available"}>
          {product.status === "Available" ? "Thêm vào giỏ hàng ↗" : product.status === "Reserved" ? "Đang được giữ chỗ" : "Sản phẩm đã bán"}
        </button>
      </div>
    </section>
  </div>;
}
