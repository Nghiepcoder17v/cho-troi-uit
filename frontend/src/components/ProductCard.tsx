import type { Product } from "../types";
import { money } from "../utils/format";
import { ProductMediaGallery } from "./ProductMediaGallery";

type ProductCardProps = {
  product: Product;
  onView: () => void;
  isFavorite?: boolean;
  favoriteBusy?: boolean;
  onToggleFavorite?: () => void;
};

export function ProductCard({
  product, onView, isFavorite = false, favoriteBusy = false, onToggleFavorite,
}: ProductCardProps) {
  return <article className="product-card">
    <div className={`product-image image-${product.product_id % 4}`}>
      <span className="condition-tag">{product.condition}</span>
      <ProductMediaGallery media={product.media} productId={product.product_id} productTitle={product.title} fallbackGlyph={["⌨", "◒", "▤", "✦"][product.product_id % 4]} mode="card" />
      {onToggleFavorite && <button
        type="button"
        className={`product-favorite-toggle ${isFavorite ? "is-saved" : ""}`}
        aria-label={isFavorite ? `Bỏ lưu ${product.title}` : `Lưu ${product.title}`}
        aria-pressed={isFavorite}
        disabled={favoriteBusy}
        onClick={onToggleFavorite}
      >{isFavorite ? "♥" : "♡"}</button>}
    </div>
    <div className="product-info"><div><h3>{product.title}</h3><p>{product.seller.full_name}</p></div><strong>{money.format(product.price)}</strong></div>
    <button className="buy-button" onClick={onView}>{product.status === "Available" ? "Xem chi tiết" : product.status === "Reserved" ? "Đang giữ chỗ" : "Đã bán"} <span>↗</span></button>
  </article>;
}
