import type { Product } from "../types";
import { money } from "../utils/format";

type CartDrawerProps = {
  cart: Product[];
  onClose: () => void;
  onRemove: (id: number) => void;
  onCheckout: () => void;
};

export function CartDrawer({ cart, onClose, onRemove, onCheckout }: CartDrawerProps) {
  const total = cart.reduce((sum, item) => sum + item.price, 0);
  return <div className="modal-backdrop drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <aside className="cart-drawer">
      <button className="close-button" onClick={onClose}>×</button>
      <p className="eyebrow">Mua có chọn lọc</p><h2>Giỏ hàng <span>{cart.length}</span></h2>
      {cart.length ? <>
        <div className="cart-items">{cart.map((item) => <div className="cart-item" key={item.product_id}>
          <span className={`mini-image image-${item.product_id % 4}`}>{["⌨", "◒", "▤", "✦"][item.product_id % 4]}</span>
          <div><strong>{item.title}</strong><small>{money.format(item.price)}</small></div>
          <button onClick={() => onRemove(item.product_id)}>×</button>
        </div>)}</div>
        <div className="cart-total"><span>Tạm tính</span><strong>{money.format(total)}</strong></div>
        <button className="dark-button submit-button" onClick={onCheckout}>Gửi yêu cầu mua ↗</button>
        <small className="muted">Mỗi yêu cầu sẽ giữ chỗ sản phẩm và chờ người bán chấp nhận. Thanh toán và bàn giao diễn ra trực tiếp bên ngoài nền tảng.</small>
      </> : <div className="empty-state">Giỏ hàng đang trống.</div>}
    </aside>
  </div>;
}
