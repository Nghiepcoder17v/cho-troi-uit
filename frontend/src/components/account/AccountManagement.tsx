export function OrderSummary({ item }: { item: TransactionHistory }) {
  const label: Record<string, string> = {
    Pending: "Đang chờ", Accepted: "Đã chấp nhận", Completed: "Hoàn tất", Cancelled: "Đã hủy",
  };
  return <div className="account-order-summary">
    <div><strong>{item.product_title}</strong><small>#{item.transaction_id} · {new Date(item.transaction_date).toLocaleDateString("vi-VN")}</small></div>
    <div><strong>{money.format(item.amount)}</strong><small>{label[item.status]}</small></div>
  </div>;
}

export function ProfileEditor({ user, onSave }: {
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

export function ProductManagement({ products, onUpdated }: { products: Product[]; onUpdated: () => Promise<void> }) {
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

export function ManagedProductCard({ product, editing, onEdit, onUpdated, onError }: {
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
      <div className={"mini-image image-" + (product.product_id % 4)}><ProductMediaGallery media={product.media} productId={product.product_id} productTitle={product.title} fallbackGlyph={["⌨", "◒", "▤", "✦"][product.product_id % 4]} mode="thumbnail" /></div>
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
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { updateProduct } from "../../api";
import type { Condition, Product, TransactionHistory, User } from "../../types";
import { conditions, money } from "../../utils/format";
import { ProductMediaGallery } from "../ProductMediaGallery";

