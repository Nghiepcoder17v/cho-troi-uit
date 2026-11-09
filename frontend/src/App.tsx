import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  buyProduct,
  createProduct,
  getMe,
  getMyProducts,
  getPurchases,
  listCategories,
  listProducts,
  login,
  register,
} from "./api";
import type { Category, Condition, Product, TransactionHistory, User } from "./types";

const money = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" });
const conditions: Condition[] = ["Brand New", "Like New", "Good", "Fair"];

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<"market" | "sell" | "account">("market");
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<number | undefined>();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [purchases, setPurchases] = useState<TransactionHistory[]>([]);
  const [myProducts, setMyProducts] = useState<Product[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const refreshProducts = async () => {
    try {
      setError("");
      setProducts((await listProducts({ q: query, category_id: category })).data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tải sản phẩm");
    }
  };

  useEffect(() => {
    void Promise.all([listCategories(), refreshProducts()])
      .then(([loadedCategories]) => setCategories(loadedCategories))
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể tải dữ liệu"));
    if (localStorage.getItem("access_token")) void getMe().then(setUser).catch(() => localStorage.removeItem("access_token"));
  }, []);

  useEffect(() => {
    if (view === "market") void refreshProducts();
    if (view === "account" && user) void Promise.all([getMyProducts(), getPurchases()]).then(([mine, bought]) => {
      setMyProducts(mine);
      setPurchases(bought);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể tải tài khoản"));
  }, [view, category]);

  const featured = useMemo(() => products.slice(0, 3), [products]);

  const signOut = () => {
    localStorage.removeItem("access_token");
    setUser(null);
    setView("market");
  };

  const handleBuy = async (product: Product) => {
    if (!user) {
      setAuthMode("login");
      setShowAuth(true);
      return;
    }
    try {
      await buyProduct(product.product_id, product.price);
      setNotice("Đặt mua thành công — sản phẩm đã được giữ cho bạn.");
      await refreshProducts();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể đặt mua");
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setView("market")} aria-label="Về trang chủ">
          <span className="brand-mark">ct</span>
          <span>chợ trời <b>UIT</b></span>
        </button>
        <nav className="nav-links">
          <button className={view === "market" ? "active" : ""} onClick={() => setView("market")}>Khám phá</button>
          <button onClick={() => setView("sell")}>Đăng bán</button>
          {user && <button className={view === "account" ? "active" : ""} onClick={() => setView("account")}>Tài khoản</button>}
        </nav>
        {user ? (
          <button className="user-chip" onClick={() => setView("account")}><span>{user.full_name.slice(0, 1)}</span>{user.full_name}</button>
        ) : <button className="outline-button" onClick={() => { setAuthMode("login"); setShowAuth(true); }}>Đăng nhập</button>}
      </header>

      {notice && <div className="toast success">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {error && <div className="toast error">{error}<button onClick={() => setError("")}>×</button></div>}

      {view === "market" && <main>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Mua bán trong cộng đồng UIT</p>
            <h1>Đồ hay quanh đây.<br /><em>Giá thật, người thật.</em></h1>
            <p className="hero-description">Tìm món đồ tiếp theo của bạn từ những người bạn cùng trường.</p>
            <div className="search-bar"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void refreshProducts()} placeholder="Tìm bàn phím, giáo trình, xe máy..." /><button onClick={() => void refreshProducts()}>Tìm kiếm</button></div>
            <div className="hero-meta"><span><i className="dot green" /> Giao dịch an tâm</span><span><i className="dot orange" /> Cộng đồng UIT</span></div>
          </div>
          <div className="hero-art"><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><div className="art-card"><span>NEW</span><strong>Find your<br />next thing.</strong><small>01 / 04</small></div></div>
        </section>
        <section className="section-block">
          <div className="section-heading"><div><p className="eyebrow">Bắt đầu từ đâu?</p><h2>Khám phá theo danh mục</h2></div><button className="text-button" onClick={() => setCategory(undefined)}>Xem tất cả <span>↗</span></button></div>
          <div className="category-row">{categories.map((item, index) => <button className={`category-pill category-${index % 4}`} key={item.category_id} onClick={() => setCategory(item.category_id)}><span>{["▦", "⌁", "⌨", "✦"][index % 4]}</span>{item.category_name}</button>)}</div>
        </section>
        <section className="section-block product-section">
          <div className="section-heading"><div><p className="eyebrow">Mới đăng gần đây</p><h2>{category ? categories.find((item) => item.category_id === category)?.category_name : "Món đồ đang được tìm kiếm"}</h2></div><span className="result-count">{products.length} tin đăng</span></div>
          <div className="product-grid">{products.map((product) => <ProductCard key={product.product_id} product={product} onBuy={() => void handleBuy(product)} />)}</div>
          {!products.length && <div className="empty-state">Chưa có sản phẩm phù hợp. Hãy thử từ khóa khác.</div>}
        </section>
        {featured.length > 0 && <section className="wide-banner"><div><p className="eyebrow">Dành cho bạn</p><h2>Một vòng quanh chợ,<br />một món đồ vừa ý.</h2><button className="dark-button" onClick={() => setQuery("")}>Xem thêm sản phẩm <span>↗</span></button></div><div className="banner-shape">✳</div></section>}
      </main>}

      {view === "sell" && <SellView user={user} categories={categories} onLogin={() => { setAuthMode("login"); setShowAuth(true); }} onCreated={() => { setView("market"); void refreshProducts(); setNotice("Tin đăng của bạn đã được tạo."); }} />}
      {view === "account" && user && <AccountView user={user} products={myProducts} purchases={purchases} onSignOut={signOut} />}
      {view === "account" && !user && <div className="empty-state account-empty">Đăng nhập để xem tài khoản của bạn.</div>}
      {showAuth && <AuthModal mode={authMode} onClose={() => setShowAuth(false)} onModeChange={setAuthMode} onAuthenticated={(nextUser) => { setUser(nextUser); setShowAuth(false); }} />}
      <footer><span>chợ trời UIT</span><span>Made for the UIT community · 2026</span></footer>
    </div>
  );
}

function ProductCard({ product, onBuy }: { product: Product; onBuy: () => void }) {
  return <article className="product-card"><div className={`product-image image-${product.product_id % 4}`}><span className="condition-tag">{product.condition}</span><span className="image-glyph">{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span></div><div className="product-info"><div><h3>{product.title}</h3><p>{product.seller.full_name}</p></div><strong>{money.format(product.price)}</strong></div><button className="buy-button" onClick={onBuy} disabled={product.status !== "Available"}>{product.status === "Available" ? "Xem & đặt mua" : "Đã bán"} <span>↗</span></button></article>;
}

function SellView({ user, categories, onLogin, onCreated }: { user: User | null; categories: Category[]; onLogin: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ title: "", description: "", price: "", category_id: categories[0]?.category_id ?? 1, condition: "Good" as Condition });
  const [error, setError] = useState("");
  if (!user) return <div className="auth-gate"><p className="eyebrow">Đăng bán</p><h1>Chia sẻ món đồ<br /><em>với cộng đồng.</em></h1><p>Đăng nhập để bắt đầu tạo tin đăng của bạn.</p><button className="dark-button" onClick={onLogin}>Đăng nhập ngay ↗</button></div>;
  const submit = async (event: FormEvent) => { event.preventDefault(); try { await createProduct({ ...form, price: Number(form.price), category_id: Number(form.category_id) }); onCreated(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể đăng bán"); } };
  return <main className="form-page"><div className="form-intro"><p className="eyebrow">Đăng bán một món đồ</p><h1>Cho món đồ của bạn<br /><em>một vòng đời mới.</em></h1><p>Thông tin rõ ràng giúp món đồ tìm được chủ mới nhanh hơn.</p></div><form className="listing-form" onSubmit={(event) => void submit(event)}>{error && <div className="form-error">{error}</div>}<label>Tiêu đề<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ví dụ: Bàn phím cơ Keychron K2" /></label><div className="two-fields"><label>Giá bán (VND)<input required type="number" min="0" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="450000" /></label><label>Tình trạng<select value={form.condition} onChange={(event) => setForm({ ...form, condition: event.target.value as Condition })}>{conditions.map((item) => <option key={item}>{item}</option>)}</select></label></div><label>Danh mục<select value={form.category_id} onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })}>{categories.map((item) => <option key={item.category_id} value={item.category_id}>{item.category_name}</option>)}</select></label><label>Mô tả<textarea rows={4} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Món đồ còn mới không? Có phụ kiện gì đi kèm?" /></label><button className="dark-button submit-button">Đăng tin ngay <span>↗</span></button></form></main>;
}

function AccountView({ user, products, purchases, onSignOut }: { user: User; products: Product[]; purchases: TransactionHistory[]; onSignOut: () => void }) {
  return <main className="account-page"><div className="account-header"><div className="profile-avatar">{user.full_name.slice(0, 1)}</div><div><p className="eyebrow">Tài khoản của bạn</p><h1>{user.full_name}</h1><p>{user.email} · {user.major ?? "Sinh viên UIT"}</p></div><button className="outline-button" onClick={onSignOut}>Đăng xuất</button></div><div className="account-columns"><section><div className="section-heading"><h2>Tin đăng của tôi</h2><span className="result-count">{products.length}</span></div>{products.length ? products.map((product) => <div className="history-row" key={product.product_id}><span className={`mini-image image-${product.product_id % 4}`}>{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span><div><strong>{product.title}</strong><small>{product.status} · {money.format(product.price)}</small></div></div>) : <p className="muted">Bạn chưa đăng tin nào.</p>}</section><section><div className="section-heading"><h2>Lịch sử mua</h2><span className="result-count">{purchases.length}</span></div>{purchases.length ? purchases.map((item) => <div className="history-row" key={item.transaction_id}><span className="mini-image image-2">↗</span><div><strong>{item.product_title}</strong><small>{item.status} · {money.format(item.amount)}</small></div></div>) : <p className="muted">Bạn chưa có giao dịch mua.</p>}</section></div></main>;
}

function AuthModal({ mode, onClose, onModeChange, onAuthenticated }: { mode: "login" | "register"; onClose: () => void; onModeChange: (mode: "login" | "register") => void; onAuthenticated: (user: User) => void }) {
  const [form, setForm] = useState({ email: "", student_id: "", full_name: "", major: "", password: "" });
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); try { if (mode === "register") await register(form); const session = await login(form.email, form.password); localStorage.setItem("access_token", session.token); onAuthenticated(await getMe()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Thông tin chưa hợp lệ"); } };
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><form className="auth-modal" onSubmit={(event) => void submit(event)}><button type="button" className="close-button" onClick={onClose}>×</button><p className="eyebrow">{mode === "login" ? "Chào mừng trở lại" : "Tham gia cộng đồng"}</p><h2>{mode === "login" ? "Đăng nhập." : "Tạo tài khoản."}</h2>{error && <div className="form-error">{error}</div>}{mode === "register" && <><label>Họ và tên<input required value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label><label>MSSV<input required pattern="\d{8}" value={form.student_id} onChange={(event) => setForm({ ...form, student_id: event.target.value })} placeholder="25520001" /></label><label>Ngành học<input value={form.major} onChange={(event) => setForm({ ...form, major: event.target.value })} /></label></>}<label>Email UIT<input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="mssv@gm.uit.edu.vn" /></label><label>Mật khẩu<input required minLength={8} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label><button className="dark-button submit-button">{mode === "login" ? "Đăng nhập ↗" : "Tạo tài khoản ↗"}</button><p className="switch-auth">{mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"} <button type="button" onClick={() => onModeChange(mode === "login" ? "register" : "login")}>{mode === "login" ? "Đăng ký" : "Đăng nhập"}</button></p></form></div>;
}

export default App;
