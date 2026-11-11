import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { ThemeToggle } from "./components/ThemeToggle";
import type { FormEvent } from "react";
import {
  acceptTransaction,
  buyProduct,
  createTransactionReview,
  cancelTransaction,
  confirmTransactionCompletion,
  createProduct,
  changeMyPassword,
  getMe,
  getMyProducts,
  getProduct,
  getPurchases,
  getSales,
  getPublicProfile,
  getPublicProducts,
  getSellerReputation,
  getUserReviews,
  updateReview,
  updateMyProfile,
  updateProduct,
  rejectTransaction,
  listCategories,
  listProducts,
  login,
  logout,
  register,
} from "./api";
import type { Category, Condition, OrderAction, Pagination, Product, PublicProfile, Review, SellerReputation, TransactionHistory, User } from "./types";

const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" });
const conditions: Condition[] = ["Brand New", "Like New", "Good", "Fair"];

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<"market" | "sell" | "account" | "public-profile">("market");
  const [publicProfileUserId, setPublicProfileUserId] = useState<number | null>(null);
  const [publicProfileReturnView, setPublicProfileReturnView] = useState<"market" | "account" | "public-profile">("market");
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try {
      return localStorage.getItem("theme") === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<number | undefined>();
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<Pagination>({ current_page: 1, page_size: 12, total_items: 0, total_pages: 0 });
  const [categories, setCategories] = useState<Category[]>([]);
  const [purchases, setPurchases] = useState<TransactionHistory[]>([]);
  const [sales, setSales] = useState<TransactionHistory[]>([]);
  const [myProducts, setMyProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<Product[]>(() => {
    try { return JSON.parse(localStorage.getItem("cart") ?? "[]") as Product[]; } catch { return []; }
  });
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showCart, setShowCart] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute(
      "content",
      theme === "dark" ? "#0B0F14" : "#F3F6F9",
    );
    try {
      localStorage.setItem("theme", theme);
    } catch {
      // Theme still works for this session when browser storage is unavailable.
    }
  }, [theme]);

  const refreshProducts = async () => {
    try {
      setError("");
      const result = await listProducts({ q: query, category_id: category, page });
      setProducts(result.data);
      setPagination(result.pagination ?? { current_page: page, page_size: 12, total_items: result.data.length, total_pages: 1 });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tải sản phẩm");
    }
  };

  useEffect(() => {
    void listCategories()
      .then((loadedCategories) => setCategories(loadedCategories))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu"));
    try {
      // Remove the bearer token left by older versions of the app.
      localStorage.removeItem("access_token");
    } catch {
      // Cookie authentication still works when browser storage is unavailable.
    }
    void getMe().then(setUser).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (view === "market") void refreshProducts();
    if (view === "account" && user) void Promise.all([getMyProducts(), getPurchases(), getSales()]).then(([mine, bought, sold]) => {
      setMyProducts(mine);
      setPurchases(bought);
      setSales(sold);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể tải tài khoản"));
  }, [view, category, page]);

  const refreshAccount = async () => {
    const [mine, bought, sold] = await Promise.all([getMyProducts(), getPurchases(), getSales()]);
    setMyProducts(mine);
    setPurchases(bought);
    setSales(sold);
  };

  const handleOrderAction = async (transactionId: number, action: OrderAction) => {
    try {
      const actions: Record<OrderAction, (id: number) => Promise<void>> = {
        accept: acceptTransaction,
        reject: rejectTransaction,
        cancel: cancelTransaction,
        "confirm-completion": confirmTransactionCompletion,
      };
      await actions[action](transactionId);
      await refreshAccount();
      await refreshProducts();
      const messages: Record<OrderAction, string> = {
        accept: "Đã chấp nhận yêu cầu mua.",
        reject: "Đã từ chối yêu cầu và mở bán lại sản phẩm.",
        cancel: "Đã hủy giao dịch và giải phóng sản phẩm.",
        "confirm-completion": "Đã ghi nhận xác nhận hoàn tất.",
      };
      setNotice(messages[action]);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể cập nhật giao dịch");
    }
  };

  const featured = useMemo(() => products.slice(0, 3), [products]);

  const signOut = async () => {
    let logoutFailed = false;
    try {
      await logout();
    } catch {
      logoutFailed = true;
    }
    localStorage.removeItem("cart");
    setCart([]);
    setUser(null);
    setView("market");
    setPublicProfileUserId(null);
    setShowCart(false);
    setError(logoutFailed ? "Không thể xác nhận đăng xuất với máy chủ. Hãy thử lại." : "");
  };

  const openPublicProfile = (userId: number) => {
    const returnView = view === "public-profile"
      ? publicProfileReturnView
      : view === "account" ? "account" : "market";
    setPublicProfileReturnView(returnView);
    setPublicProfileUserId(userId);
    setSelectedProduct(null);
    setView("public-profile");
  };

  const saveMyProfile = async (body: { full_name?: string; major?: string | null }) => {
    const updated = await updateMyProfile(body);
    setUser(updated);
    setNotice("Hồ sơ cá nhân đã được cập nhật.");
    setError("");
    return updated;
  };

  const handleProductUpdated = async () => {
    await refreshAccount();
    setNotice("Tin đăng đã được cập nhật.");
    setError("");
  };

  const addToCart = (product: Product) => {
    if (!user) {
      setAuthMode("login");
      setShowAuth(true);
      return;
    }
    if (!cart.some((item) => item.product_id === product.product_id)) {
      const next = [...cart, product];
      setCart(next);
      localStorage.setItem("cart", JSON.stringify(next));
      setNotice("Đã thêm sản phẩm vào giỏ hàng.");
    }
  };

  const removeFromCart = (productId: number) => {
    const next = cart.filter((item) => item.product_id !== productId);
    setCart(next);
    localStorage.setItem("cart", JSON.stringify(next));
  };

  const checkout = async () => {
    if (!cart.length) return;
    const submittedIds: number[] = [];
    const failures: string[] = [];

    for (const cachedProduct of cart) {
      try {
        const latestProduct = await getProduct(cachedProduct.product_id);
        if (latestProduct.status !== "Available") {
          throw new Error("Sản phẩm không còn khả dụng");
        }
        // Luôn dùng giá/trạng thái vừa đọc từ API, không tin dữ liệu cache localStorage.
        await buyProduct(latestProduct.product_id, latestProduct.price);
        submittedIds.push(latestProduct.product_id);
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : "Không thể gửi yêu cầu";
        failures.push(`${cachedProduct.title}: ${message}`);
      }
    }

    const remaining = cart.filter((item) => !submittedIds.includes(item.product_id));
    setCart(remaining);
    if (remaining.length) localStorage.setItem("cart", JSON.stringify(remaining));
    else localStorage.removeItem("cart");
    setShowCart(false);

    if (submittedIds.length) {
      setNotice(`${submittedIds.length} yêu cầu mua đã được gửi. Sản phẩm đang được giữ chỗ chờ người bán phản hồi.`);
    }
    await refreshProducts();
    if (user) {
      try {
        await refreshAccount();
      } catch (reason) {
        failures.push(reason instanceof Error ? `Không thể làm mới dữ liệu tài khoản: ${reason.message}` : "Không thể làm mới dữ liệu tài khoản");
      }
    }
    if (failures.length) setError(`Một số sản phẩm chưa gửi được yêu cầu:\n${failures.join("\n")}`);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button
          className="brand"
          onClick={() => { setView("market"); setMobileNavOpen(false); }}
          aria-label="Về trang chủ"
          type="button"
        >
          <span className="brand-mark">ct</span>
          <span>chợ trời <b>UIT</b></span>
        </button>

        <nav
          className={`nav-links ${mobileNavOpen ? "is-open" : ""}`}
          id="primary-navigation"
          aria-label="Điều hướng chính"
        >
          <button
            type="button"
            className={view === "market" ? "active" : ""}
            aria-current={view === "market" ? "page" : undefined}
            onClick={() => { setView("market"); setMobileNavOpen(false); }}
          >
            Khám phá
          </button>
          <button
            type="button"
            className={view === "sell" ? "active" : ""}
            aria-current={view === "sell" ? "page" : undefined}
            onClick={() => { setView("sell"); setMobileNavOpen(false); }}
          >
            Đăng bán
          </button>
          {user && (
            <button
              type="button"
              className={view === "account" ? "active" : ""}
              aria-current={view === "account" ? "page" : undefined}
              onClick={() => { setView("account"); setMobileNavOpen(false); }}
            >
              Tài khoản
            </button>
          )}
        </nav>

        <div className="header-actions">
          {user ? (
            <button className="user-chip" onClick={() => { setView("account"); setMobileNavOpen(false); }} type="button">
              <span>{user.full_name.slice(0, 1)}</span>
              <span className="user-chip-name">{user.full_name}</span>
            </button>
          ) : (
            <button
              className="outline-button"
              onClick={() => { setAuthMode("login"); setShowAuth(true); }}
              type="button"
            >
              Đăng nhập
            </button>
          )}
          <button
            className="cart-button"
            onClick={() => { setShowCart(true); setMobileNavOpen(false); }}
            aria-label={`Mở giỏ hàng, ${cart.length} sản phẩm`}
            type="button"
          >
            Giỏ hàng <b>{cart.length}</b>
          </button>
          <ThemeToggle theme={theme} onToggle={() => setTheme((current) => current === "dark" ? "light" : "dark")} />
          <button
            className={`menu-toggle ${mobileNavOpen ? "is-open" : ""}`}
            type="button"
            aria-expanded={mobileNavOpen}
            aria-controls="primary-navigation"
            aria-label={mobileNavOpen ? "Đóng menu" : "Mở menu"}
            onClick={() => setMobileNavOpen((open) => !open)}
          >
            <span aria-hidden="true">{mobileNavOpen ? "×" : "☰"}</span>
          </button>
        </div>
      </header>

      {notice && <div className="toast success">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {error && <div className="toast error">{error}<button onClick={() => setError("")}>×</button></div>}

      {view === "market" && <main>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Mua bán trong cộng đồng UIT</p>
            <h1>Đồ hay quanh đây.<br /><em>Giá thật, người thật.</em></h1>
            <p className="hero-description">Tìm món đồ tiếp theo của bạn từ những người bạn cùng trường.</p>
            <div className="search-bar"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && (page !== 1 ? setPage(1) : void refreshProducts())} placeholder="Tìm bàn phím, giáo trình, xe máy..." /><button onClick={() => (page !== 1 ? setPage(1) : void refreshProducts())}>Tìm kiếm</button></div>
            <div className="hero-meta"><span><i className="dot green" /> Giao dịch an tâm</span><span><i className="dot orange" /> Cộng đồng UIT</span></div>
          </div>
          <div className="hero-art"><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><div className="art-card"><span>NEW</span><strong>Find your<br />next thing.</strong><small>01 / 04</small></div></div>
        </section>
        <section className="section-block">
          <div className="section-heading"><div><p className="eyebrow">Bắt đầu từ đâu?</p><h2>Khám phá theo danh mục</h2></div><button className="text-button" onClick={() => { setCategory(undefined); setPage(1); }}>Xem tất cả <span>↗</span></button></div>
          <div className="category-row">{categories.map((item, index) => <button className={`category-pill category-${index % 4}`} key={item.category_id} onClick={() => { setCategory(item.category_id); setPage(1); }}><span>{["▦", "⌁", "⌨", "✦"][index % 4]}</span>{item.category_name}</button>)}</div>
        </section>
        <section className="section-block product-section">
          <div className="section-heading"><div><p className="eyebrow">Mới đăng gần đây</p><h2>{category ? categories.find((item) => item.category_id === category)?.category_name : "Món đồ đang được tìm kiếm"}</h2></div><span className="result-count">{pagination.total_items} tin đăng</span></div>
          <div className="product-grid">{products.map((product) => <ProductCard key={product.product_id} product={product} onView={() => setSelectedProduct(product)} />)}</div>
          {pagination.total_pages > 1 && <nav className="pagination" aria-label="Phân trang sản phẩm">
            <button type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>← Trước</button>
            <span>Trang {pagination.current_page} / {pagination.total_pages}</span>
            <button type="button" disabled={page >= pagination.total_pages} onClick={() => setPage((current) => Math.min(pagination.total_pages, current + 1))}>Sau →</button>
          </nav>}
          {!products.length && <div className="empty-state">Chưa có sản phẩm phù hợp. Hãy thử từ khóa khác.</div>}
        </section>
        {featured.length > 0 && <section className="wide-banner"><div><p className="eyebrow">Dành cho bạn</p><h2>Một vòng quanh chợ,<br />một món đồ vừa ý.</h2><button className="dark-button" onClick={() => setQuery("")}>Xem thêm sản phẩm <span>↗</span></button></div><div className="banner-shape">✳</div></section>}
      </main>}

      {view === "sell" && <SellView user={user} categories={categories} onLogin={() => { setAuthMode("login"); setShowAuth(true); }} onCreated={() => { setView("market"); void refreshProducts(); setNotice("Tin đăng của bạn đã được tạo."); }} />}
      {view === "account" && user && <AccountView
        user={user}
        products={myProducts}
        purchases={purchases}
        sales={sales}
        cart={cart}
        theme={theme}
        onToggleTheme={() => setTheme((current) => current === "dark" ? "light" : "dark")}
        onSignOut={signOut}
        onAction={(id, action) => void handleOrderAction(id, action)}
        onReviewSaved={refreshAccount}
        onRemoveCart={removeFromCart}
        onCheckout={() => void checkout()}
        onProfileUpdated={saveMyProfile}
        onProductUpdated={handleProductUpdated}
        onOpenPublicProfile={openPublicProfile}
      />}
      {view === "account" && !user && <div className="empty-state account-empty">Đăng nhập để xem tài khoản của bạn.</div>}
      {view === "public-profile" && publicProfileUserId !== null && <PublicProfilePage
        userId={publicProfileUserId}
        onBack={() => setView(publicProfileReturnView)}
        onViewProduct={(product) => setSelectedProduct(product)}
      />}
      {selectedProduct && <ProductDetail
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
        onAdd={() => { addToCart(selectedProduct); setSelectedProduct(null); }}
        onViewSeller={() => openPublicProfile(selectedProduct.seller.user_id)}
      />}
      {showCart && <CartDrawer cart={cart} onClose={() => setShowCart(false)} onRemove={removeFromCart} onCheckout={() => void checkout()} />}
      {showAuth && <AuthModal mode={authMode} onClose={() => setShowAuth(false)} onModeChange={setAuthMode} onAuthenticated={(nextUser) => { setUser(nextUser); setShowAuth(false); }} />}
      <footer><span>chợ trời UIT</span><span>Made for the UIT community · 2026</span></footer>
    </div>
  );
}

function ProductCard({ product, onView }: { product: Product; onView: () => void }) {
  return <article className="product-card"><div className={`product-image image-${product.product_id % 4}`}><span className="condition-tag">{product.condition}</span><span className="image-glyph">{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span></div><div className="product-info"><div><h3>{product.title}</h3><p>{product.seller.full_name}</p></div><strong>{money.format(product.price)}</strong></div><button className="buy-button" onClick={onView}>{product.status === "Available" ? "Xem chi tiết" : product.status === "Reserved" ? "Đang giữ chỗ" : "Đã bán"} <span>↗</span></button></article>;
}

function ProductDetail({ product, onClose, onAdd, onViewSeller }: { product: Product; onClose: () => void; onAdd: () => void; onViewSeller: () => void }) {
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

function CartDrawer({ cart, onClose, onRemove, onCheckout }: { cart: Product[]; onClose: () => void; onRemove: (id: number) => void; onCheckout: () => void }) {
  const total = cart.reduce((sum, item) => sum + item.price, 0);
  return <div className="modal-backdrop drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><aside className="cart-drawer"><button className="close-button" onClick={onClose}>×</button><p className="eyebrow">Mua có chọn lọc</p><h2>Giỏ hàng <span>{cart.length}</span></h2>{cart.length ? <><div className="cart-items">{cart.map((item) => <div className="cart-item" key={item.product_id}><span className={`mini-image image-${item.product_id % 4}`}>{["⌨", "◒", "▤", "✦"][item.product_id % 4]}</span><div><strong>{item.title}</strong><small>{money.format(item.price)}</small></div><button onClick={() => onRemove(item.product_id)}>×</button></div>)}</div><div className="cart-total"><span>Tạm tính</span><strong>{money.format(total)}</strong></div><button className="dark-button submit-button" onClick={onCheckout}>Gửi yêu cầu mua ↗</button><small className="muted">Mỗi yêu cầu sẽ giữ chỗ sản phẩm và chờ người bán chấp nhận. Thanh toán và bàn giao diễn ra trực tiếp bên ngoài nền tảng.</small></> : <div className="empty-state">Giỏ hàng đang trống.</div>}</aside></div>;
}

function SellView({ user, categories, onLogin, onCreated }: { user: User | null; categories: Category[]; onLogin: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ title: "", description: "", price: "", category_id: categories[0]?.category_id ?? 1, condition: "Good" as Condition });
  const [error, setError] = useState("");
  if (!user) return <div className="auth-gate"><p className="eyebrow">Đăng bán</p><h1>Chia sẻ món đồ<br /><em>với cộng đồng.</em></h1><p>Đăng nhập để bắt đầu tạo tin đăng của bạn.</p><button className="dark-button" onClick={onLogin}>Đăng nhập ngay ↗</button></div>;
  const submit = async (event: FormEvent) => { event.preventDefault(); try { await createProduct({ ...form, price: Number(form.price), category_id: Number(form.category_id) }); onCreated(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể đăng bán"); } };
  return <main className="form-page"><div className="form-intro"><p className="eyebrow">Đăng bán một món đồ</p><h1>Cho món đồ của bạn<br /><em>một vòng đời mới.</em></h1><p>Thông tin rõ ràng giúp món đồ tìm được chủ mới nhanh hơn.</p></div><form className="listing-form" onSubmit={(event) => void submit(event)}>{error && <div className="form-error">{error}</div>}<label>Tiêu đề<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ví dụ: Bàn phím cơ Keychron K2" /></label><div className="two-fields"><label>Giá bán (VND)<input required type="number" min="0" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="450000" /></label><label>Tình trạng<select value={form.condition} onChange={(event) => setForm({ ...form, condition: event.target.value as Condition })}>{conditions.map((item) => <option key={item}>{item}</option>)}</select></label></div><label>Danh mục<select value={form.category_id} onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })}>{categories.map((item) => <option key={item.category_id} value={item.category_id}>{item.category_name}</option>)}</select></label><label>Mô tả<textarea rows={4} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Món đồ còn mới không? Có phụ kiện gì đi kèm?" /></label><button className="dark-button submit-button">Đăng tin ngay <span>↗</span></button></form></main>;
}

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

function AccountView({
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

function OrderSummary({ item }: { item: TransactionHistory }) {
  const label: Record<string, string> = {
    Pending: "Đang chờ", Accepted: "Đã chấp nhận", Completed: "Hoàn tất", Cancelled: "Đã hủy",
  };
  return <div className="account-order-summary">
    <div><strong>{item.product_title}</strong><small>#{item.transaction_id} · {new Date(item.transaction_date).toLocaleDateString("vi-VN")}</small></div>
    <div><strong>{money.format(item.amount)}</strong><small>{label[item.status]}</small></div>
  </div>;
}

function ProfileEditor({ user, onSave }: {
  user: User;
  onSave: (body: { full_name?: string; major?: string | null }) => Promise<User>;
}) {
  const [fullName, setFullName] = useState(user.full_name);
  const [major, setMajor] = useState(user.major ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setFullName(user.full_name);
    setMajor(user.major ?? "");
  }, [user.full_name, user.major]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true); setMessage(""); setError("");
    try {
      await onSave({ full_name: fullName, major: major.trim() || null });
      setMessage("Thông tin đã được lưu.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể cập nhật hồ sơ");
    } finally {
      setSaving(false);
    }
  };

  return <section className="account-section-content">
    <div className="account-card account-form-card">
      <div className="account-card-heading"><div><p className="eyebrow">THÔNG TIN CÁ NHÂN</p><h2>Hồ sơ của bạn</h2><p>Chỉ họ tên và ngành học có thể chỉnh sửa tại đây.</p></div></div>
      <form className="account-form" onSubmit={(event) => void submit(event)}>
        <div className="account-form-grid">
          <label>Họ và tên<input required minLength={2} maxLength={100} value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
          <label>Ngành học<input maxLength={50} value={major} onChange={(event) => setMajor(event.target.value)} placeholder="Ví dụ: Kỹ thuật phần mềm" /></label>
          <label>Email UIT<input value={user.email} readOnly disabled /></label>
          <label>Mã số sinh viên<input value={user.student_id} readOnly disabled /></label>
        </div>
        {message && <p className="form-success" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="dark-button" type="submit" disabled={saving}>{saving ? "Đang lưu..." : "Lưu thay đổi"}</button>
      </form>
    </div>
    <p className="account-privacy-note">Email UIT và mã số sinh viên được khóa để bảo vệ định danh tài khoản. Hai thông tin này không hiển thị trên trang cá nhân công khai.</p>
  </section>;
}

function ProductManagement({ products, onUpdated }: { products: Product[]; onUpdated: () => Promise<void> }) {
  const [filter, setFilter] = useState<"All" | Product["status"]>("All");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const visibleProducts = products.filter((item) => filter === "All" || item.status === filter);

  return <section className="account-section-content">
    <div className="account-toolbar">
      <div><strong>{visibleProducts.length} tin đăng</strong><small>Quản lý trạng thái và thông tin sản phẩm của bạn.</small></div>
      <select aria-label="Lọc tin đăng" value={filter} onChange={(event) => setFilter(event.target.value as "All" | Product["status"])}>
        <option value="All">Tất cả trạng thái</option><option value="Available">Đang mở bán</option><option value="Reserved">Đang giữ chỗ</option><option value="Sold">Đã bán</option><option value="Hidden">Đã ẩn</option>
      </select>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {visibleProducts.length ? <div className="managed-product-list">{visibleProducts.map((product) => <ManagedProductCard
      key={product.product_id}
      product={product}
      editing={editingId === product.product_id}
      onEdit={() => { setEditingId(editingId === product.product_id ? null : product.product_id); setError(""); }}
      onUpdated={async () => { await onUpdated(); setEditingId(null); }}
      onError={setError}
    />)}</div> : <div className="empty-state">Không có tin đăng ở trạng thái này.</div>}
  </section>;
}

function ManagedProductCard({ product, editing, onEdit, onUpdated, onError }: {
  product: Product;
  editing: boolean;
  onEdit: () => void;
  onUpdated: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState(product.title);
  const [description, setDescription] = useState(product.description ?? "");
  const [price, setPrice] = useState(String(product.price));
  const [condition, setCondition] = useState<Condition>(product.condition);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTitle(product.title); setDescription(product.description ?? "");
    setPrice(String(product.price)); setCondition(product.condition);
  }, [product.product_id, product.title, product.description, product.price, product.condition]);

  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); onError("");
    try {
      await updateProduct(product.product_id, { title, description, price: Number(price), condition });
      await onUpdated();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Không thể lưu tin đăng");
    } finally { setSaving(false); }
  };

  const toggleVisibility = async () => {
    setSaving(true); onError("");
    try {
      await updateProduct(product.product_id, { status: product.status === "Hidden" ? "Available" : "Hidden" });
      await onUpdated();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Không thể đổi trạng thái tin đăng");
    } finally { setSaving(false); }
  };

  return <article className="managed-product-card">
    <div className="managed-product-summary">
      <span className={"mini-image image-" + (product.product_id % 4)}>{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span>
      <div className="managed-product-copy"><strong>{product.title}</strong><small>{money.format(product.price)} · {product.condition}</small></div>
      <span className={"managed-product-status status-" + product.status.toLowerCase()}>{product.status}</span>
    </div>
    {product.status === "Reserved" && <p className="muted managed-product-note">Sản phẩm đang giữ chỗ nên tạm khóa chỉnh sửa.</p>}
    {product.status === "Sold" && <p className="muted managed-product-note">Sản phẩm đã bán, thông tin tin đăng được giữ nguyên.</p>}
    <div className="managed-product-actions">
      {(product.status === "Available" || product.status === "Hidden") && <button type="button" className="text-button" onClick={onEdit}>{editing ? "Đóng chỉnh sửa" : "Chỉnh sửa tin"}</button>}
      {(product.status === "Available" || product.status === "Hidden") && <button type="button" className="outline-button" disabled={saving} onClick={() => void toggleVisibility()}>{product.status === "Hidden" ? "Mở bán lại" : "Ẩn tin đăng"}</button>}
    </div>
    {editing && (product.status === "Available" || product.status === "Hidden") && <form className="managed-product-editor" onSubmit={(event) => void save(event)}>
      <label>Tiêu đề<input required minLength={1} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <div className="two-fields"><label>Giá bán (VND)<input required type="number" min="0" max="99999999.99" step="0.01" value={price} onChange={(event) => setPrice(event.target.value)} /></label><label>Tình trạng<select value={condition} onChange={(event) => setCondition(event.target.value as Condition)}>{conditions.map((item) => <option key={item}>{item}</option>)}</select></label></div>
      <label>Mô tả<textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
      <button type="submit" className="dark-button" disabled={saving}>{saving ? "Đang lưu..." : "Lưu tin đăng"}</button>
    </form>}
  </article>;
}

function OrderListPanel({ title, items, role, onAction, onReviewSaved }: {
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

function CartPanel({ cart, onRemove, onCheckout, onBrowse }: {
  cart: Product[];
  onRemove: (id: number) => void;
  onCheckout: () => void;
  onBrowse: () => void;
}) {
  const total = cart.reduce((sum, item) => sum + item.price, 0);
  return <section className="account-section-content">
    {cart.length ? <>
      <div className="account-toolbar"><div><strong>{cart.length} sản phẩm</strong><small>Giỏ hàng được lưu trên trình duyệt này.</small></div><strong className="account-cart-total">{money.format(total)}</strong></div>
      <div className="managed-product-list">{cart.map((item) => <article className="managed-product-card cart-managed-card" key={item.product_id}>
        <span className={"mini-image image-" + (item.product_id % 4)}>{["⌨", "◒", "▤", "✦"][item.product_id % 4]}</span>
        <div className="managed-product-copy"><strong>{item.title}</strong><small>{money.format(item.price)} · {item.seller.full_name}</small></div>
        <button type="button" className="text-button" onClick={() => onRemove(item.product_id)}>Xóa</button>
      </article>)}</div>
      <div className="account-cart-footer"><div><small>Tạm tính</small><strong>{money.format(total)}</strong></div><button type="button" className="dark-button" onClick={onCheckout}>Gửi yêu cầu mua ↗</button></div>
      <p className="account-privacy-note">Giỏ hàng chưa giữ chỗ sản phẩm. Hệ thống sẽ kiểm tra lại giá và trạng thái trước khi gửi từng yêu cầu mua.</p>
    </> : <div className="empty-state"><h3>Giỏ hàng đang trống</h3><p>Thêm sản phẩm từ khu vực Khám phá để bắt đầu.</p><button type="button" className="dark-button" onClick={onBrowse}>Khám phá sản phẩm</button></div>}
  </section>;
}

function AccountSettings({ theme, onToggleTheme, onSignOut }: {
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onSignOut: () => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setMessage(""); setError("");
    if (newPassword !== confirmPassword) { setError("Mật khẩu mới và xác nhận không khớp."); return; }
    setSaving(true);
    try {
      await changeMyPassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setMessage("Mật khẩu đã được thay đổi.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể đổi mật khẩu");
    } finally { setSaving(false); }
  };

  return <section className="account-section-content account-settings-grid">
    <section className="account-card">
      <div className="account-card-heading"><div><p className="eyebrow">GIAO DIỆN</p><h2>Chủ đề hiển thị</h2><p>Thay đổi giao diện sáng hoặc tối cho thiết bị này.</p></div></div>
      <div className="account-theme-control"><div><strong>{theme === "dark" ? "Dark Mode" : "Light Mode"}</strong><small>Chủ đề hiện tại</small></div><button type="button" className="outline-button" onClick={onToggleTheme}>Chuyển sang {theme === "dark" ? "Light" : "Dark"}</button></div>
    </section>
    <section className="account-card">
      <div className="account-card-heading"><div><p className="eyebrow">BẢO MẬT</p><h2>Đổi mật khẩu</h2><p>Xác minh mật khẩu hiện tại trước khi đặt mật khẩu mới.</p></div></div>
      <form className="account-form account-password-form" onSubmit={(event) => void submit(event)}>
        <label>Mật khẩu hiện tại<input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
        <label>Mật khẩu mới<input required minLength={8} maxLength={72} type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
        <label>Xác nhận mật khẩu mới<input required minLength={8} maxLength={72} type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
        {message && <p className="form-success" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="dark-button" type="submit" disabled={saving}>{saving ? "Đang cập nhật..." : "Cập nhật mật khẩu"}</button>
      </form>
    </section>
    <section className="account-card account-danger-card">
      <div><p className="eyebrow">PHIÊN ĐĂNG NHẬP</p><h2>Đăng xuất khỏi tài khoản</h2><p>Đăng xuất trên trình duyệt hiện tại. Giỏ hàng lưu cục bộ vẫn được giữ lại.</p></div>
      <button type="button" className="outline-button" onClick={onSignOut}>Đăng xuất</button>
    </section>
  </section>;
}

function PublicProfilePage({ userId, onBack, onViewProduct }: {
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

function OrderCard({
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

function ReviewEditor({
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

function ReviewList({ reviews, emptyText }: { reviews: Review[]; emptyText: string }) {
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

function AuthModal({ mode, onClose, onModeChange, onAuthenticated }: { mode: "login" | "register"; onClose: () => void; onModeChange: (mode: "login" | "register") => void; onAuthenticated: (user: User) => void }) {
  const [form, setForm] = useState({ email: "", student_id: "", full_name: "", major: "", password: "" });
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); try { if (mode === "register") await register(form); await login(form.email, form.password); onAuthenticated(await getMe()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Thông tin chưa hợp lệ"); } };
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><form className="auth-modal" onSubmit={(event) => void submit(event)}><button type="button" className="close-button" onClick={onClose}>×</button><p className="eyebrow">{mode === "login" ? "Chào mừng trở lại" : "Tham gia cộng đồng"}</p><h2>{mode === "login" ? "Đăng nhập." : "Tạo tài khoản."}</h2>{error && <div className="form-error">{error}</div>}{mode === "register" && <><label>Họ và tên<input required value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label><label>MSSV<input required pattern="\d{8}" value={form.student_id} onChange={(event) => setForm({ ...form, student_id: event.target.value })} placeholder="25520001" /></label><label>Ngành học<input value={form.major} onChange={(event) => setForm({ ...form, major: event.target.value })} /></label></>}<label>Email UIT<input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="mssv@gm.uit.edu.vn" /></label><label>Mật khẩu<input required minLength={8} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label><button className="dark-button submit-button">{mode === "login" ? "Đăng nhập ↗" : "Tạo tài khoản ↗"}</button><p className="switch-auth">{mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"} <button type="button" onClick={() => onModeChange(mode === "login" ? "register" : "login")}>{mode === "login" ? "Đăng ký" : "Đăng nhập"}</button></p></form></div>;
}

export default App;
