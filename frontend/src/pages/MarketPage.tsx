import type { Category, Pagination, Product } from "../types";
import { ProductCard } from "../components/ProductCard";

type MarketPageProps = {
  categories: Category[];
  products: Product[];
  page: number;
  pagination: Pagination;
  query: string;
  categoryId?: number;
  hasFeatured: boolean;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onCategoryChange: (value?: number) => void;
  onPageChange: (value: number) => void;
  onViewProduct: (product: Product) => void;
};

export function MarketPage({
  categories, products, page, pagination, query, categoryId, hasFeatured,
  onQueryChange, onSearch, onCategoryChange, onPageChange, onViewProduct,
}: MarketPageProps) {
  return <main>
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">Mua bán trong cộng đồng UIT</p>
        <h1>Đồ hay quanh đây.<br /><em>Giá thật, người thật.</em></h1>
        <p className="hero-description">Tìm món đồ tiếp theo của bạn từ những người bạn cùng trường.</p>
        <div className="search-bar"><span>⌕</span><input value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSearch()} placeholder="Tìm bàn phím, giáo trình, xe máy..." /><button onClick={onSearch}>Tìm kiếm</button></div>
        <div className="hero-meta"><span><i className="dot green" /> Giao dịch an tâm</span><span><i className="dot orange" /> Cộng đồng UIT</span></div>
      </div>
      <div className="hero-art"><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><div className="art-card"><span>NEW</span><strong>Find your<br />next thing.</strong><small>01 / 04</small></div></div>
    </section>
    <section className="section-block">
      <div className="section-heading"><div><p className="eyebrow">Bắt đầu từ đâu?</p><h2>Khám phá theo danh mục</h2></div><button className="text-button" onClick={() => onCategoryChange(undefined)}>Xem tất cả <span>↗</span></button></div>
      <div className="category-row">{categories.map((item, index) => <button className={`category-pill category-${index % 4}`} key={item.category_id} onClick={() => onCategoryChange(item.category_id)}><span>{["▦", "⌁", "⌨", "✦"][index % 4]}</span>{item.category_name}</button>)}</div>
    </section>
    <section className="section-block product-section">
      <div className="section-heading"><div><p className="eyebrow">Mới đăng gần đây</p><h2>{categoryId ? categories.find((item) => item.category_id === categoryId)?.category_name : "Món đồ đang được tìm kiếm"}</h2></div><span className="result-count">{pagination.total_items} tin đăng</span></div>
      <div className="product-grid">{products.map((product) => <ProductCard key={product.product_id} product={product} onView={() => onViewProduct(product)} />)}</div>
      {pagination.total_pages > 1 && <nav className="pagination" aria-label="Phân trang sản phẩm">
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))}>← Trước</button>
        <span>Trang {pagination.current_page} / {pagination.total_pages}</span>
        <button type="button" disabled={page >= pagination.total_pages} onClick={() => onPageChange(Math.min(pagination.total_pages, page + 1))}>Sau →</button>
      </nav>}
      {!products.length && <div className="empty-state">Chưa có sản phẩm phù hợp. Hãy thử từ khóa khác.</div>}
    </section>
    {hasFeatured && <section className="wide-banner"><div><p className="eyebrow">Dành cho bạn</p><h2>Một vòng quanh chợ,<br />một món đồ vừa ý.</h2><button className="dark-button" onClick={() => onQueryChange("")}>Xem thêm sản phẩm <span>↗</span></button></div><div className="banner-shape">✳</div></section>}
  </main>;
}
