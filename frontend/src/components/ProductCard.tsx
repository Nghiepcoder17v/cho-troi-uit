import type { Product } from "../types";
import { money } from "../utils/format";

export function ProductCard({ product, onView }: { product: Product; onView: () => void }) {
  return <article className="product-card"><div className={`product-image image-${product.product_id % 4}`}><span className="condition-tag">{product.condition}</span><span className="image-glyph">{["⌨", "◒", "▤", "✦"][product.product_id % 4]}</span></div><div className="product-info"><div><h3>{product.title}</h3><p>{product.seller.full_name}</p></div><strong>{money.format(product.price)}</strong></div><button className="buy-button" onClick={onView}>{product.status === "Available" ? "Xem chi tiết" : product.status === "Reserved" ? "Đang giữ chỗ" : "Đã bán"} <span>↗</span></button></article>;
}
