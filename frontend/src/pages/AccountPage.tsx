export function AccountView({
  user, products, purchases, sales, cart, theme, onToggleTheme, onSignOut, onAction, onReviewSaved,
  onRemoveCart, onCheckout, onProfileUpdated, onProductUpdated, onOpenPublicProfile,
}: {
  user: User;
  products: Product[];
  purchases: TransactionHistory[];
  sales: TransactionHistory[];
  cart: Product[];
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onSignOut: () => void;
  onAction: (id: number, action: OrderAction) => void;
  onReviewSaved: () => Promise<void>;
  onRemoveCart: (id: number) => void;
  onCheckout: () => void;
  onProfileUpdated: (body: { full_name?: string; major?: string | null }) => Promise<User>;
  onProductUpdated: () => Promise<void>;
  onOpenPublicProfile: (id: number) => void;
}) {
  const [section, setSection] = useState<AccountSection>("overview");
  const [reputation, setReputation] = useState<SellerReputation | null>(null);
  const [receivedReviews, setReceivedReviews] = useState<Review[]>([]);
  const completedPurchases = purchases.filter((item) => item.status === "Completed");
  const completedSales = sales.filter((item) => item.status === "Completed");
  const spent = completedPurchases.reduce((sum, item) => sum + item.amount, 0);
  const earned = completedSales.reduce((sum, item) => sum + item.amount, 0);
  const selected = accountNavigation.find((item) => item.id === section) ?? accountNavigation[0];

  useEffect(() => {
    let active = true;
    Promise.all([
      getSellerReputation(user.user_id),
      getUserReviews(user.user_id),
    ]).then(([nextReputation, nextReviews]) => {
      if (!active) return;
      setReputation(nextReputation);
      setReceivedReviews(nextReviews);
    }).catch(() => {
      if (active) setReceivedReviews([]);
    });
    return () => { active = false; };
  }, [user.user_id, purchases, sales]);

  return <main className="account-page account-center-page">
    <div className="account-center-shell">
      <aside className="account-sidebar" aria-label="Điều hướng tài khoản">
        <div className="account-sidebar-user">
          <div className="profile-avatar">{user.full_name.slice(0, 1)}</div>
          <div><strong>{user.full_name}</strong><small>{user.major || "Sinh viên UIT"}</small></div>
        </div>
        <nav className="account-side-nav">
          <p className="account-nav-caption">TÀI KHOẢN</p>
          {accountNavigation.map((item) => <button
            key={item.id}
            type="button"
            className={section === item.id ? "active" : ""}
            aria-current={section === item.id ? "page" : undefined}
            onClick={() => setSection(item.id)}
          >
            <span aria-hidden="true">{item.icon}</span>{item.label}
            {item.id === "cart" && cart.length > 0 && <small>{cart.length}</small>}
          </button>)}
          <button type="button" className="account-public-link" onClick={() => onOpenPublicProfile(user.user_id)}>
            <span aria-hidden="true">↗</span>Trang cá nhân công khai
          </button>
          <button type="button" className="account-signout-link" onClick={onSignOut}>
            <span aria-hidden="true">⇥</span>Đăng xuất
          </button>
        </nav>
      </aside>

      <section className="account-main-panel">
        <header className="account-main-heading">
          <div>
            <p className="eyebrow">ACCOUNT CENTER</p>
            <h1>{selected.label}</h1>
            <p>{selected.description}</p>
          </div>
          <div className="account-heading-avatar">{user.full_name.slice(0, 1)}</div>
        </header>

        {section === "overview" && <section className="account-section-content">
          <div className="account-welcome">
            <div><p className="eyebrow">Xin chào</p><h2>{user.full_name}</h2><p>Quản lý hoạt động mua bán và danh tiếng của bạn trong cộng đồng UIT.</p></div>
            <button type="button" className="outline-button" onClick={() => onOpenPublicProfile(user.user_id)}>Xem trang cá nhân ↗</button>
          </div>
          <div className="account-stats account-stats-grid">
            <div><small>Tổng đã chi</small><strong>{money.format(spent)}</strong><small>{completedPurchases.length} đơn hoàn tất</small></div>
            <div><small>Tổng doanh thu</small><strong>{money.format(earned)}</strong><small>{completedSales.length} đơn hoàn tất</small></div>
            <div><small>Tin đăng</small><strong>{products.length}</strong><small>{products.filter((item) => item.status === "Available").length} đang mở bán</small></div>
            <div><small>Uy tín cộng đồng</small><strong>{reputation?.score == null ? "Chưa có" : reputation.score.toFixed(1) + "/5"}</strong><small>{reputation?.review_count ?? 0} đánh giá</small></div>
          </div>
          <div className="account-overview-grid">
            <section className="account-card">
              <div className="section-heading"><div><p className="eyebrow">Giao dịch</p><h2>Đơn mua gần đây</h2></div><button type="button" className="text-button" onClick={() => setSection("purchases")}>Xem tất cả ↗</button></div>
              {purchases.length ? purchases.slice(0, 3).map((item) => <OrderSummary key={item.transaction_id} item={item} />) : <p className="muted">Bạn chưa có yêu cầu mua nào.</p>}
            </section>
            <section className="account-card">
              <div className="section-heading"><div><p className="eyebrow">Tin đăng</p><h2>Sản phẩm của tôi</h2></div><button type="button" className="text-button" onClick={() => setSection("listings")}>Quản lý ↗</button></div>
              {products.length ? products.slice(0, 3).map((product) => <div className="history-row" key={product.product_id}>
                <span className={"mini-image image-" + (product.product_id % 4)}>{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span>
                <div><strong>{product.title}</strong><small>{product.status} · {money.format(product.price)}</small></div>
              </div>) : <p className="muted">Bạn chưa đăng tin nào.</p>}
            </section>
          </div>
          <section className="account-card account-received-reviews">
            <div className="section-heading"><div><p className="eyebrow">Danh tiếng</p><h2>Đánh giá tôi nhận được</h2></div><span className="result-count">{receivedReviews.length}</span></div>
            <ReviewList reviews={receivedReviews.slice(0, 4)} emptyText="Bạn chưa nhận được đánh giá nào." />
            {reputation && <div className="rating-distribution" aria-label="Phân phối số lượt đánh giá">
              {[5, 4, 3, 2, 1].map((rating) => <div className="rating-row" key={rating}>
                <span>{rating} ★</span><span className="rating-track"><i style={{ width: (reputation.review_count ? (reputation.rating_distribution[String(rating) as keyof typeof reputation.rating_distribution] / reputation.review_count) * 100 : 0) + "%" }} /></span>
                <small>{reputation.rating_distribution[String(rating) as keyof typeof reputation.rating_distribution]}</small>
              </div>)}
            </div>}
          </section>
        </section>}

        {section === "profile" && <ProfileEditor user={user} onSave={onProfileUpdated} />}
        {section === "listings" && <ProductManagement products={products} onUpdated={onProductUpdated} />}
        {section === "purchases" && <OrderListPanel title="Đơn mua" items={purchases} role="buyer" onAction={onAction} onReviewSaved={onReviewSaved} />}
        {section === "sales" && <OrderListPanel title="Đơn bán" items={sales} role="seller" onAction={onAction} onReviewSaved={onReviewSaved} />}
        {section === "cart" && <CartPanel cart={cart} onRemove={onRemoveCart} onCheckout={onCheckout} onBrowse={() => setSection("overview")} />}
        {section === "settings" && <AccountSettings theme={theme} onToggleTheme={onToggleTheme} onSignOut={onSignOut} />}
      </section>
    </div>
  </main>;
}
import { useEffect, useState } from "react";
import { getSellerReputation, getUserReviews } from "../api";
import type { OrderAction, Product, Review, SellerReputation, TransactionHistory, User } from "../types";
import { money } from "../utils/format";
import { AccountSettings, CartPanel } from "../components/account/AccountExtras";
import { OrderSummary, ProductManagement, ProfileEditor } from "../components/account/AccountManagement";
import { OrderListPanel } from "../components/account/OrderPanels";
import { ReviewList } from "../components/ReviewList";

type AccountSection = "overview" | "profile" | "listings" | "purchases" | "sales" | "cart" | "settings";

const accountNavigation: { id: AccountSection; label: string; icon: string; description: string }[] = [
  { id: "overview", label: "Tổng quan", icon: "⌂", description: "Hoạt động và thống kê tài khoản" },
  { id: "profile", label: "Hồ sơ cá nhân", icon: "◎", description: "Thông tin tài khoản riêng tư" },
  { id: "listings", label: "Tin đăng của tôi", icon: "▤", description: "Quản lý sản phẩm đang đăng bán" },
  { id: "purchases", label: "Đơn mua", icon: "↓", description: "Theo dõi các yêu cầu mua" },
  { id: "sales", label: "Đơn bán", icon: "↑", description: "Xử lý các yêu cầu từ người mua" },
  { id: "cart", label: "Giỏ hàng", icon: "▣", description: "Sản phẩm bạn đang quan tâm" },
  { id: "settings", label: "Cài đặt", icon: "⚙", description: "Giao diện và bảo mật tài khoản" },
];

