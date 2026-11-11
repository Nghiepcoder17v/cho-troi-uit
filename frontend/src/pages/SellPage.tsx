import { useState } from "react";
import type { FormEvent } from "react";
import { createProduct } from "../api";
import type { Category, Condition, User } from "../types";
import { conditions } from "../utils/format";

type SellPageProps = {
  user: User | null;
  categories: Category[];
  onLogin: () => void;
  onCreated: () => void;
};

export function SellPage({ user, categories, onLogin, onCreated }: SellPageProps) {
  const [form, setForm] = useState({ title: "", description: "", price: "", category_id: categories[0]?.category_id ?? 1, condition: "Good" as Condition });
  const [error, setError] = useState("");
  if (!user) return <div className="auth-gate"><p className="eyebrow">Đăng bán</p><h1>Chia sẻ món đồ<br /><em>với cộng đồng.</em></h1><p>Đăng nhập để bắt đầu tạo tin đăng của bạn.</p><button className="dark-button" onClick={onLogin}>Đăng nhập ngay ↗</button></div>;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await createProduct({ ...form, price: Number(form.price), category_id: Number(form.category_id) });
      onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể đăng bán");
    }
  };
  return <main className="form-page">
    <div className="form-intro"><p className="eyebrow">Đăng bán một món đồ</p><h1>Cho món đồ của bạn<br /><em>một vòng đời mới.</em></h1><p>Thông tin rõ ràng giúp món đồ tìm được chủ mới nhanh hơn.</p></div>
    <form className="listing-form" onSubmit={(event) => void submit(event)}>
      {error && <div className="form-error">{error}</div>}
      <label>Tiêu đề<input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ví dụ: Bàn phím cơ Keychron K2" /></label>
      <div className="two-fields">
        <label>Giá bán (VND)<input required type="number" min="0" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="450000" /></label>
        <label>Tình trạng<select value={form.condition} onChange={(event) => setForm({ ...form, condition: event.target.value as Condition })}>{conditions.map((item) => <option key={item}>{item}</option>)}</select></label>
      </div>
      <label>Danh mục<select value={form.category_id} onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })}>{categories.map((item) => <option key={item.category_id} value={item.category_id}>{item.category_name}</option>)}</select></label>
      <label>Mô tả<textarea rows={4} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Món đồ còn mới không? Có phụ kiện gì đi kèm?" /></label>
      <button className="dark-button submit-button">Đăng tin ngay <span>↗</span></button>
    </form>
  </main>;
}
