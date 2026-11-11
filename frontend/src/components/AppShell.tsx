import type { ReactNode } from "react";
import type { User } from "../types";

export type AppView = "market" | "explore" | "sell" | "account" | "public-profile";

type AppShellProps = {
  user: User | null;
  view: AppView;
  mobileNavOpen: boolean;
  cartCount: number;
  notice: string;
  error: string;
  children: ReactNode;
  onNavigate: (view: AppView) => void;
  onOpenLogin: () => void;
  onOpenCart: () => void;
  onToggleMenu: () => void;
  onCloseMenu: () => void;
  onClearNotice: () => void;
  onClearError: () => void;
};

export function AppShell({
  user, view, mobileNavOpen, cartCount, notice, error, children,
  onNavigate, onOpenLogin, onOpenCart, onToggleMenu, onCloseMenu, onClearNotice, onClearError,
}: AppShellProps) {
  const navigate = (nextView: AppView) => {
    onNavigate(nextView);
    onCloseMenu();
  };

  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => navigate("market")} aria-label="Về trang chủ" type="button">
        <span className="brand-mark">ct</span><span>chợ trời <b>UIT</b></span>
      </button>
      <nav className={`nav-links ${mobileNavOpen ? "is-open" : ""}`} id="primary-navigation" aria-label="Điều hướng chính">
        <button type="button" className={view === "market" ? "active" : ""} aria-current={view === "market" ? "page" : undefined} onClick={() => navigate("market")}>Trang chủ</button>
        <button type="button" className={view === "explore" ? "active" : ""} aria-current={view === "explore" ? "page" : undefined} onClick={() => navigate("explore")}>Khám phá</button>
        <button type="button" className={view === "sell" ? "active" : ""} aria-current={view === "sell" ? "page" : undefined} onClick={() => navigate("sell")}>Đăng bán</button>
        {user && <button type="button" className={view === "account" ? "active" : ""} aria-current={view === "account" ? "page" : undefined} onClick={() => navigate("account")}>Tài khoản</button>}
      </nav>
      <div className="header-actions">
        {user ? <button className="user-chip" onClick={() => navigate("account")} type="button"><span>{user.full_name.slice(0, 1)}</span><span className="user-chip-name">{user.full_name}</span></button> : <button className="outline-button" onClick={onOpenLogin} type="button">Đăng nhập</button>}
        <button className="cart-button" onClick={onOpenCart} aria-label={`Mở giỏ hàng, ${cartCount} sản phẩm`} type="button">Giỏ hàng <b>{cartCount}</b></button>
        <button className={`menu-toggle ${mobileNavOpen ? "is-open" : ""}`} type="button" aria-expanded={mobileNavOpen} aria-controls="primary-navigation" aria-label={mobileNavOpen ? "Đóng menu" : "Mở menu"} onClick={onToggleMenu}>
          <span aria-hidden="true">{mobileNavOpen ? "×" : "☰"}</span>
        </button>
      </div>
    </header>
    {notice && <div className="toast success" role="status" aria-live="polite">{notice}<button type="button" aria-label="Đóng thông báo" onClick={onClearNotice}>×</button></div>}
    {error && <div className="toast error" role="alert" aria-live="assertive">{error}<button type="button" aria-label="Đóng thông báo lỗi" onClick={onClearError}>×</button></div>}
    {children}
    <footer><span>chợ trời UIT</span><span>Made for the UIT community · 2026</span></footer>
  </div>;
}
