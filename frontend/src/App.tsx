import { useEffect, useState } from "react";
import { AppShell, type AppView } from "./components/AppShell";
import { ProductDetailModal } from "./components/ProductDetailModal";
import { CartDrawer } from "./components/CartDrawer";
import { AuthModal } from "./components/AuthModal";
import { AccountView } from "./pages/AccountPage";
import { MarketPage } from "./pages/MarketPage";
import { PublicProfilePage } from "./pages/PublicProfilePage";
import { SellPage } from "./pages/SellPage";
import {
  acceptTransaction,
  buyProduct,
  cancelTransaction,
  confirmTransactionCompletion,
  getMe,
  getMyProducts,
  getProduct,
  getPurchases,
  getSales,
  updateMyProfile,
  rejectTransaction,
  listCategories,
  listProducts,
  logout,
} from "./api";
import type { Category, OrderAction, Pagination, Product, TransactionHistory, User } from "./types";
import { useTheme } from "./hooks/useTheme";

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<AppView>("market");
  const [publicProfileUserId, setPublicProfileUserId] = useState<number | null>(null);
  const [publicProfileReturnView, setPublicProfileReturnView] = useState<"market" | "account" | "public-profile">("market");
  const { theme, toggleTheme } = useTheme();
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
    <AppShell
      user={user}
      view={view}
      mobileNavOpen={mobileNavOpen}
      cartCount={cart.length}
      theme={theme}
      notice={notice}
      error={error}
      onNavigate={setView}
      onOpenLogin={() => { setAuthMode("login"); setShowAuth(true); }}
      onOpenCart={() => { setShowCart(true); setMobileNavOpen(false); }}
      onToggleTheme={toggleTheme}
      onToggleMenu={() => setMobileNavOpen((open) => !open)}
      onCloseMenu={() => setMobileNavOpen(false)}
      onClearNotice={() => setNotice("")}
      onClearError={() => setError("")}
    >
      {view === "market" && <MarketPage
        categories={categories}
        products={products}
        page={page}
        pagination={pagination}
        query={query}
        categoryId={category}
        hasFeatured={products.length > 0}
        onQueryChange={setQuery}
        onSearch={() => (page !== 1 ? setPage(1) : void refreshProducts())}
        onCategoryChange={(value) => { setCategory(value); setPage(1); }}
        onPageChange={setPage}
        onViewProduct={setSelectedProduct}
      />}
      {view === "sell" && <SellPage user={user} categories={categories} onLogin={() => { setAuthMode("login"); setShowAuth(true); }} onCreated={() => { setView("market"); void refreshProducts(); setNotice("Tin đăng của bạn đã được tạo."); }} />}
      {view === "account" && user && <AccountView
        user={user}
        products={myProducts}
        purchases={purchases}
        sales={sales}
        cart={cart}
        theme={theme}
        onToggleTheme={toggleTheme}
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
        onViewProduct={setSelectedProduct}
      />}
      {selectedProduct && <ProductDetailModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
        onAdd={() => { addToCart(selectedProduct); setSelectedProduct(null); }}
        onViewSeller={() => openPublicProfile(selectedProduct.seller.user_id)}
      />}
      {showCart && <CartDrawer cart={cart} onClose={() => setShowCart(false)} onRemove={removeFromCart} onCheckout={() => void checkout()} />}
      {showAuth && <AuthModal mode={authMode} onClose={() => setShowAuth(false)} onModeChange={setAuthMode} onAuthenticated={(nextUser) => { setUser(nextUser); setShowAuth(false); }} />}
    </AppShell>
  );
}

export default App;
