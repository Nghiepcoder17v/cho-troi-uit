import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { ThemeToggle } from "./components/ThemeToggle";
import type { FormEvent } from "react";
import {
  acceptTransaction,
  buyProduct,
  cancelTransaction,
  confirmTransactionCompletion,
  createProduct,
  getMe,
  getMyProducts,
  getProduct,
  getPurchases,
  getSales,
  getSellerReputation,
  rejectTransaction,
  listCategories,
  listProducts,
  login,
  register,
} from "./api";
import type { Category, Condition, OrderAction, Pagination, Product, SellerReputation, TransactionHistory, User } from "./types";

const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" });
const conditions: Condition[] = ["Brand New", "Like New", "Good", "Fair"];

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<"market" | "sell" | "account">("market");
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
    if (localStorage.getItem("access_token")) void getMe().then(setUser).catch(() => localStorage.removeItem("access_token"));
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

  const signOut = () => {
    localStorage.removeItem("access_token");
    setUser(null);
    setView("market");
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
    if (failures.length) setError(`Một số sản phẩm chưa gửi được yêu cầu:\\n${failures.join("\\n")}`);
    await refreshProducts();
    if (user) await refreshAccount();
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
      {view === "account" && user && <AccountView user={user} products={myProducts} purchases={purchases} sales={sales} onSignOut={signOut} onAction={(id, action) => void handleOrderAction(id, action)} />}
      {view === "account" && !user && <div className="empty-state account-empty">Đăng nhập để xem tài khoản của bạn.</div>}
      {selectedProduct && <ProductDetail product={selectedProduct} onClose={() => setSelectedProduct(null)} onAdd={() => { addToCart(selectedProduct); setSelectedProduct(null); }} />}
      {showCart && <CartDrawer cart={cart} onClose={() => setShowCart(false)} onRemove={removeFromCart} onCheckout={() => void checkout()} />}
      {showAuth && <AuthModal mode={authMode} onClose={() => setShowAuth(false)} onModeChange={setAuthMode} onAuthenticated={(nextUser) => { setUser(nextUser); setShowAuth(false); }} />}
      <footer><span>chợ trời UIT</span><span>Made for the UIT community · 2026</span></footer>
    </div>
  );
}

function ProductCard({ product, onView }: { product: Product; onView: () => void }) {
  return <article className="product-card"><div className={`product-image image-${product.product_id % 4}`}><span className="condition-tag">{product.condition}</span><span className="image-glyph">{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span></div><div className="product-info"><div><h3>{product.title}</h3><p>{product.seller.full_name}</p></div><strong>{money.format(product.price)}</strong></div><button className="buy-button" onClick={onView}>{product.status === "Available" ? "Xem chi tiết" : product.status === "Reserved" ? "Đang giữ chỗ" : "Đã bán"} <span>↗</span></button></article>;
}

function ProductDetail({ product, onClose, onAdd }: { product: Product; onClose: () => void; onAdd: () => void }) {
  const [reputation, setReputation] = useState<SellerReputation | null>(null);
  useEffect(() => { void getSellerReputation(product.seller.user_id).then(setReputation); }, [product.seller.user_id]);
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="detail-modal"><button className="close-button" onClick={onClose}>×</button><div className={`detail-image image-${product.product_id % 4}`}><span className="image-glyph">{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span></div><div className="detail-content"><p className="eyebrow">{product.condition} · Chi tiết sản phẩm</p><h2>{product.title}</h2><strong className="detail-price">{money.format(product.price)}</strong><p className="detail-description">{product.description || "Người bán chưa thêm mô tả cho sản phẩm này."}</p><div className="trust-card"><span className="trust-icon">✓</span><div><strong>Lịch sử giao dịch</strong><small>{reputation ? `${reputation.completed_sales} giao dịch hoàn tất` : "Đang tải số liệu giao dịch..."}</small></div></div><button className="dark-button submit-button" onClick={onAdd} disabled={product.status !== "Available"}>{product.status === "Available" ? "Thêm vào giỏ hàng ↗" : product.status === "Reserved" ? "Đang được giữ chỗ" : "Sản phẩm đã bán"}</button></div></section></div>;
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

function AccountView({
  user, products, purchases, sales, onSignOut, onAction,
}: {
  user: User;
  products: Product[];
  purchases: TransactionHistory[];
  sales: TransactionHistory[];
  onSignOut: () => void;
  onAction: (id: number, action: OrderAction) => void;
}) {
  const completedPurchases = purchases.filter((item) => item.status === "Completed");
  const completedSales = sales.filter((item) => item.status === "Completed");
  const spent = completedPurchases.reduce((sum, item) => sum + item.amount, 0);
  const earned = completedSales.reduce((sum, item) => sum + item.amount, 0);
  return <main className="account-page">
    <div className="account-header">
      <div className="profile-avatar">{user.full_name.slice(0, 1)}</div>
      <div><p className="eyebrow">Tài khoản của bạn</p><h1>{user.full_name}</h1><p>{user.email} · {user.major ?? "Sinh viên UIT"}</p></div>
      <button className="outline-button" onClick={onSignOut}>Đăng xuất</button>
    </div>
    <div className="account-stats">
      <div><small>Tổng đã chi (hoàn tất)</small><strong>{money.format(spent)}</strong></div>
      <div><small>Tổng doanh thu (hoàn tất)</small><strong>{money.format(earned)}</strong></div>
      <div><small>Yêu cầu mua</small><strong>{purchases.length}</strong></div>
    </div>
    <div className="account-columns">
      <section>
        <div className="section-heading"><h2>Tin đăng của tôi</h2><span className="result-count">{products.length}</span></div>
        {products.length ? products.map((product) => <div className="history-row" key={product.product_id}>
          <span className={`mini-image image-${product.product_id % 4}`}>{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span>
          <div><strong>{product.title}</strong><small>{product.status === "Reserved" ? "Đang giữ chỗ" : product.status === "Sold" ? "Đã bán" : product.status === "Hidden" ? "Đã ẩn" : "Đang mở bán"} · {money.format(product.price)}</small></div>
        </div>) : <p className="muted">Bạn chưa đăng tin nào.</p>}
      </section>
      <section>
        <div className="section-heading"><h2>Yêu cầu mua</h2><span className="result-count">{purchases.length}</span></div>
        {purchases.length ? purchases.map((item) => <OrderCard key={item.transaction_id} item={item} role="buyer" onAction={onAction} />) : <p className="muted">Bạn chưa gửi yêu cầu mua nào.</p>}
      </section>
      <section>
        <div className="section-heading"><h2>Yêu cầu bán</h2><span className="result-count">{sales.length}</span></div>
        {sales.length ? sales.map((item) => <OrderCard key={item.transaction_id} item={item} role="seller" onAction={onAction} />) : <p className="muted">Bạn chưa có yêu cầu mua từ người khác.</p>}
      </section>
    </div>
  </main>;
}

function OrderCard({
  item, role, onAction,
}: {
  item: TransactionHistory;
  role: "buyer" | "seller";
  onAction: (id: number, action: OrderAction) => void;
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
      {item.status === "Completed" && <small className="muted">Chỉ giao dịch hoàn tất mới đủ điều kiện đánh giá.</small>}
    </div>
  </article>;
}

function AuthModal({ mode, onClose, onModeChange, onAuthenticated }: { mode: "login" | "register"; onClose: () => void; onModeChange: (mode: "login" | "register") => void; onAuthenticated: (user: User) => void }) {
  const [form, setForm] = useState({ email: "", student_id: "", full_name: "", major: "", password: "" });
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); try { if (mode === "register") await register(form); const session = await login(form.email, form.password); localStorage.setItem("access_token", session.token); onAuthenticated(await getMe()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Thông tin chưa hợp lệ"); } };
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><form className="auth-modal" onSubmit={(event) => void submit(event)}><button type="button" className="close-button" onClick={onClose}>×</button><p className="eyebrow">{mode === "login" ? "Chào mừng trở lại" : "Tham gia cộng đồng"}</p><h2>{mode === "login" ? "Đăng nhập." : "Tạo tài khoản."}</h2>{error && <div className="form-error">{error}</div>}{mode === "register" && <><label>Họ và tên<input required value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label><label>MSSV<input required pattern="\d{8}" value={form.student_id} onChange={(event) => setForm({ ...form, student_id: event.target.value })} placeholder="25520001" /></label><label>Ngành học<input value={form.major} onChange={(event) => setForm({ ...form, major: event.target.value })} /></label></>}<label>Email UIT<input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="mssv@gm.uit.edu.vn" /></label><label>Mật khẩu<input required minLength={8} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label><button className="dark-button submit-button">{mode === "login" ? "Đăng nhập ↗" : "Tạo tài khoản ↗"}</button><p className="switch-auth">{mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"} <button type="button" onClick={() => onModeChange(mode === "login" ? "register" : "login")}>{mode === "login" ? "Đăng ký" : "Đăng nhập"}</button></p></form></div>;
}

export default App;
