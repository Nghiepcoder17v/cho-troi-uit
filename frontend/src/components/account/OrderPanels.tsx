export function OrderListPanel({ title, items, role, onAction, onReviewSaved }: {
  title: string;
  items: TransactionHistory[];
  role: "buyer" | "seller";
  onAction: (id: number, action: OrderAction) => void;
  onReviewSaved: () => Promise<void>;
}) {
  const [filter, setFilter] = useState<"All" | TransactionHistory["status"]>("All");
  const filtered = items.filter((item) => filter === "All" || item.status === filter);
  return <section className="account-section-content">
    <div className="account-toolbar">
      <div><strong>{filtered.length} giao dịch</strong><small>{title} của bạn được cập nhật theo trạng thái mới nhất.</small></div>
      <select aria-label={"Lọc " + title} value={filter} onChange={(event) => setFilter(event.target.value as "All" | TransactionHistory["status"])}>
        <option value="All">Tất cả trạng thái</option><option value="Pending">Chờ phản hồi</option><option value="Accepted">Đang xử lý</option><option value="Completed">Hoàn tất</option><option value="Cancelled">Đã hủy</option>
      </select>
    </div>
    {filtered.length ? <div className="account-order-list">{filtered.map((item) => <OrderCard key={item.transaction_id} item={item} role={role} onAction={onAction} onReviewSaved={onReviewSaved} />)}</div> : <div className="empty-state">Không có giao dịch trong nhóm này.</div>}
  </section>;
}

export function OrderCard({
  item, role, onAction, onReviewSaved,
}: {
  item: TransactionHistory;
  role: "buyer" | "seller";
  onAction: (id: number, action: OrderAction) => void;
  onReviewSaved: () => Promise<void>;
}) {
  const statusLabel: Record<string, string> = {
    Pending: "Chờ người bán phản hồi",
    Accepted: "Đã chấp nhận · Chờ xác nhận hai bên",
    Completed: "Hoàn tất",
    Cancelled: "Đã hủy",
  };
  const buyerConfirmed = Boolean(item.buyer_confirmed_at);
  const sellerConfirmed = Boolean(item.seller_confirmed_at);
  const canCancel = item.status === "Pending" || item.status === "Accepted";
  const waitingForMe = role === "buyer" ? !buyerConfirmed : !sellerConfirmed;
  return <article className="order-card">
    <div className="order-card-heading">
      <span className="mini-image image-2">↗</span>
      <div><strong>{item.product_title}</strong><small>{role === "buyer" ? `Người bán: ${item.seller.full_name}` : `Người mua: ${item.buyer.full_name}`}</small></div>
      <b className={`status-pill status-${item.status.toLowerCase()}`}>{statusLabel[item.status] ?? item.status}</b>
    </div>
    <div className="order-meta"><span>{money.format(item.amount)}</span><span>#{item.transaction_id}</span></div>
    {item.status === "Accepted" && <p className="confirmation-progress">
      Người mua: {buyerConfirmed ? "đã xác nhận" : "chưa xác nhận"} · Người bán: {sellerConfirmed ? "đã xác nhận" : "chưa xác nhận"}
    </p>}
    <div className="order-actions">
      {role === "seller" && item.status === "Pending" && <>
        <button type="button" className="dark-button" onClick={() => onAction(item.transaction_id, "accept")}>Chấp nhận</button>
        <button type="button" className="outline-button" onClick={() => onAction(item.transaction_id, "reject")}>Từ chối</button>
      </>}
      {item.status === "Accepted" && waitingForMe && <button type="button" className="dark-button" onClick={() => onAction(item.transaction_id, "confirm-completion")}>Xác nhận đã hoàn tất</button>}
      {canCancel && <button type="button" className="outline-button" onClick={() => onAction(item.transaction_id, "cancel")}>Hủy giao dịch</button>}
      {item.status === "Accepted" && !waitingForMe && <small className="muted">Bạn đã xác nhận. Đang chờ bên còn lại.</small>}
    </div>
    {item.status === "Completed" && <ReviewEditor item={item} role={role} onSaved={onReviewSaved} />}
  </article>;
}

export function ReviewEditor({
  item, role, onSaved,
}: {
  item: TransactionHistory;
  role: "buyer" | "seller";
  onSaved: () => Promise<void>;
}) {
  const [rating, setRating] = useState(item.my_review?.rating ?? 5);
  const [comment, setComment] = useState(item.my_review?.comment ?? "");
  const [editing, setEditing] = useState(!item.my_review);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const otherParty = role === "buyer" ? item.seller.full_name : item.buyer.full_name;

  useEffect(() => {
    setRating(item.my_review?.rating ?? 5);
    setComment(item.my_review?.comment ?? "");
    setEditing(!item.my_review);
  }, [item.my_review?.review_id, item.my_review?.updated_at]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = { rating, comment: comment.trim() || null };
      if (item.my_review) await updateReview(item.my_review.review_id, body);
      else await createTransactionReview(item.transaction_id, body);
      await onSaved();
      setEditing(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu đánh giá");
    } finally {
      setSaving(false);
    }
  };

  return <section className="review-editor">
    {item.my_review && !editing ? <div className="review-own-summary">
      <div><strong>Đánh giá của bạn dành cho {otherParty}</strong><span className="review-stars" aria-label={`${item.my_review.rating} trên 5 sao`}>{"★".repeat(item.my_review.rating)}{"☆".repeat(5 - item.my_review.rating)}</span></div>
      {item.my_review.comment && <p>{item.my_review.comment}</p>}
      <button type="button" className="text-button" onClick={() => setEditing(true)}>Chỉnh sửa đánh giá</button>
    </div> : <form onSubmit={(event) => void submit(event)} className="review-form">
      <div className="review-form-heading">
        <strong>{item.my_review ? `Sửa đánh giá cho ${otherParty}` : `Đánh giá ${otherParty}`}</strong>
        <span className="muted">Chỉ đánh giá thật từ giao dịch hoàn tất</span>
      </div>
      <div className="review-rating-input" role="group" aria-label="Chọn số sao">
        {[1, 2, 3, 4, 5].map((value) => <button key={value} type="button" aria-label={`${value} sao`} aria-pressed={rating === value} onClick={() => setRating(value)}>{value <= rating ? "★" : "☆"}</button>)}
      </div>
      <label className="review-comment-label">Bình luận (không bắt buộc)
        <textarea value={comment} maxLength={1000} rows={3} onChange={(event) => setComment(event.target.value)} placeholder="Chia sẻ trải nghiệm giao dịch của bạn..." />
        <small>{comment.length}/1000 ký tự</small>
      </label>
      {error && <p className="form-error">{error}</p>}
      <div className="review-form-actions">
        <button type="submit" className="dark-button" disabled={saving}>{saving ? "Đang lưu..." : item.my_review ? "Lưu chỉnh sửa" : "Gửi đánh giá"}</button>
        {item.my_review && <button type="button" className="outline-button" onClick={() => { setEditing(false); setError(""); }}>Hủy</button>}
      </div>
    </form>}
  </section>;
}
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createTransactionReview, updateReview } from "../../api";
import type { OrderAction, TransactionHistory } from "../../types";
import { money } from "../../utils/format";

