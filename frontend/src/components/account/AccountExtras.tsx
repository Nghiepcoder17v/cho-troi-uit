import { useState } from "react";
import type { FormEvent } from "react";
import { changeMyPassword } from "../../api";
import type { Product } from "../../types";
import { money } from "../../utils/format";
import { ProductMediaGallery } from "../ProductMediaGallery";
import { Button, Field } from "../primitives";

export function CartPanel({ cart, onRemove, onCheckout, onBrowse }: {
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
        <span className={"mini-image image-" + (item.product_id % 4)}><ProductMediaGallery media={item.media} productId={item.product_id} productTitle={item.title} fallbackGlyph={["⌨", "◒", "▤", "✦"][item.product_id % 4]} mode="thumbnail" /></span>
        <div className="managed-product-copy"><strong>{item.title}</strong><small>{money.format(item.price)} · {item.seller.full_name}</small></div>
        <button type="button" className="text-button" onClick={() => onRemove(item.product_id)}>Xóa</button>
      </article>)}</div>
      <div className="account-cart-footer"><div><small>Tạm tính</small><strong>{money.format(total)}</strong></div><button type="button" className="dark-button" onClick={onCheckout}>Gửi yêu cầu mua ↗</button></div>
      <p className="account-privacy-note">Giỏ hàng chưa giữ chỗ sản phẩm. Hệ thống sẽ kiểm tra lại giá và trạng thái trước khi gửi từng yêu cầu mua.</p>
    </> : <div className="empty-state"><h3>Giỏ hàng đang trống</h3><p>Thêm sản phẩm từ khu vực Khám phá để bắt đầu.</p><button type="button" className="dark-button" onClick={onBrowse}>Khám phá sản phẩm</button></div>}
  </section>;
}

export function AccountSettings({ theme, onToggleTheme, onSignOut }: {
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onSignOut: () => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const closePasswordForm = () => {
    setChangingPassword(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setMessage("");
    setError("");
  };

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
      <div className="account-theme-control"><div><strong>{theme === "dark" ? "Dark Mode" : "Light Mode"}</strong><small>Chủ đề hiện tại</small></div><Button variant="outline" type="button" onClick={onToggleTheme}>Chuyển sang {theme === "dark" ? "Light" : "Dark"}</Button></div>
    </section>
    <section className="account-card">
      <div className="account-card-heading"><div><p className="eyebrow">BẢO MẬT</p><h2>Đổi mật khẩu</h2><p>Xác minh mật khẩu hiện tại trước khi đặt mật khẩu mới.</p></div></div>
      {!changingPassword ? <Button variant="outline" type="button" onClick={() => setChangingPassword(true)}>Đổi mật khẩu</Button> : <form id="account-password-form" className="account-form account-password-form" onSubmit={(event) => void submit(event)}>
        <Field label="Mật khẩu hiện tại"><input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></Field>
        <Field label="Mật khẩu mới" hint="Tối thiểu 8 ký tự."><input required minLength={8} maxLength={72} type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></Field>
        <Field label="Xác nhận mật khẩu mới"><input required minLength={8} maxLength={72} type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></Field>
        {message && <p className="form-success" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="account-form-actions">
          <Button type="submit" disabled={saving}>{saving ? "Đang cập nhật..." : "Cập nhật mật khẩu"}</Button>
          <Button variant="outline" type="button" onClick={closePasswordForm} disabled={saving}>Hủy</Button>
        </div>
      </form>}
    </section>
    <section className="account-card account-danger-card">
      <div><p className="eyebrow">PHIÊN ĐĂNG NHẬP</p><h2>Đăng xuất khỏi tài khoản</h2><p>Đăng xuất trên trình duyệt hiện tại và xóa giỏ hàng đã lưu trên thiết bị này.</p></div>
      <button type="button" className="outline-button" onClick={onSignOut}>Đăng xuất</button>
    </section>
  </section>;
}

