import type { Review } from "../types";

export function ReviewList({ reviews, emptyText }: { reviews: Review[]; emptyText: string }) {
  if (!reviews.length) return <p className="muted review-empty">{emptyText}</p>;
  return <div className="review-list">
    {reviews.map((review) => <article className="review-item" key={review.review_id}>
      <div className="review-item-heading">
        <strong>{review.reviewer.full_name}</strong>
        <span className="review-stars" aria-label={`${review.rating} trên 5 sao`}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</span>
      </div>
      <small className="review-product">{review.product_title} · Giao dịch #{review.transaction_id} · {new Date(review.created_at).toLocaleDateString("vi-VN")}</small>
      {review.comment && <p>{review.comment}</p>}
    </article>)}
  </div>;
}
