export function PublicProfilePage({ userId, onBack, onViewProduct }: {
  userId: number;
  onBack: () => void;
  onViewProduct: (product: Product) => void;
}) {
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [filter, setFilter] = useState<"All" | "Available" | "Sold">("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    Promise.all([
      getPublicProfile(userId),
      getPublicProducts(userId),
      getUserReviews(userId),
    ]).then(([nextProfile, nextProducts, nextReviews]) => {
      if (!active) return;
      setProfile(nextProfile); setProducts(nextProducts); setReviews(nextReviews);
    }).catch((reason) => {
      if (active) setError(reason instanceof Error ? reason.message : "Không thể tải trang cá nhân");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId]);

  const filtered = products.filter((item) => filter === "All" || item.status === filter);
  if (loading) return <main className="public-profile-page"><button type="button" className="text-button" onClick={onBack}>← Quay lại</button><div className="empty-state">Đang tải trang cá nhân...</div></main>;
  if (error || !profile) return <main className="public-profile-page"><button type="button" className="text-button" onClick={onBack}>← Quay lại</button><div className="empty-state">{error || "Không tìm thấy người dùng."}</div></main>;

  return <main className="public-profile-page">
    <button type="button" className="text-button public-back-link" onClick={onBack}>← Quay lại</button>
    <section className="public-profile-hero">
      <div className="public-profile-avatar">{profile.full_name.slice(0, 1)}</div>
      <div className="public-profile-intro"><p className="eyebrow">TRANG CÁ NHÂN UIT</p><h1>{profile.full_name}</h1><p>{profile.major || "Sinh viên UIT"} · Tham gia {new Date(profile.created_at).toLocaleDateString("vi-VN")}</p><small>Trang cá nhân công khai · Không hiển thị email hoặc MSSV</small></div>
      <div className="public-profile-score"><strong>{profile.score == null ? "—" : profile.score.toFixed(1) + "/5"}</strong><small>{profile.review_count} đánh giá</small><small>{profile.completed_sales} giao dịch hoàn tất</small></div>
    </section>
    <section className="public-profile-section">
      <div className="section-heading"><div><p className="eyebrow">GIAN HÀNG</p><h2>Tin đăng của {profile.full_name}</h2></div><span className="result-count">{filtered.length} sản phẩm</span></div>
      <div className="account-toolbar public-product-toolbar"><div><strong>Sản phẩm công khai</strong><small>Tin đang bán và sản phẩm đã bán.</small></div><select aria-label="Lọc sản phẩm công khai" value={filter} onChange={(event) => setFilter(event.target.value as "All" | "Available" | "Sold")}><option value="All">Tất cả</option><option value="Available">Đang bán</option><option value="Sold">Đã bán</option></select></div>
      {filtered.length ? <div className="product-grid public-product-grid">{filtered.map((product) => <ProductCard key={product.product_id} product={product} onView={() => onViewProduct(product)} />)}</div> : <div className="empty-state">Người dùng chưa có tin đăng công khai trong nhóm này.</div>}
    </section>
    <section className="public-profile-section account-card">
      <div className="section-heading"><div><p className="eyebrow">UY TÍN</p><h2>Đánh giá từ cộng đồng</h2></div><span className="result-count">{reviews.length}</span></div>
      <ReviewList reviews={reviews} emptyText="Người dùng chưa nhận được đánh giá nào." />
    </section>
  </main>;
}
import { useEffect, useState } from "react";
import { getPublicProfile, getPublicProducts, getUserReviews } from "../api";
import type { Product, PublicProfile, Review } from "../types";
import { ProductCard } from "../components/ProductCard";
import { ReviewList } from "../components/ReviewList";

