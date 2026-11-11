import type { Category, Pagination, Product } from "../types";
import { ProductCard } from "../components/ProductCard";
import { EmptyState } from "../components/primitives";

type ExplorePageProps = {
  categories: Category[];
  products: Product[];
  page: number;
  pagination: Pagination;
  query: string;
  categoryId?: number;
  loading: boolean;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onCategoryChange: (value?: number) => void;
  onClearFilters: () => void;
  onPageChange: (value: number) => void;
  onViewProduct: (product: Product) => void;
};

export function ExplorePage({
  categories, products, page, pagination, query, categoryId, loading,
  onQueryChange, onSearch, onCategoryChange, onClearFilters, onPageChange, onViewProduct,
}: ExplorePageProps) {
  const selectedCategory = categories.find((item) => item.category_id === categoryId);

  return <main className="explore-page">
    <section className="explore-heading">
      <p className="eyebrow">Chợ trời UIT</p>
      <h1>Khám phá món đồ<br /><em>đang chờ bạn.</em></h1>
      <p className="hero-description">Tìm kiếm tin đăng đang mở bán trong cộng đồng UIT.</p>
      <form className="search-bar explore-search" onSubmit={(event) => { event.preventDefault(); onSearch(); }} role="search">
        <span aria-hidden="true">⌕</span>
        <input aria-label="Tìm sản phẩm" value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Tìm bàn phím, giáo trình, xe máy..." />
        <button type="submit">Tìm kiếm</button>
      </form>
    </section>

    <section className="section-block product-section explore-results" aria-busy={loading}>
      <div className="explore-controls">
        <div className="section-heading">
          <div><p className="eyebrow">Danh mục</p><h2>{selectedCategory?.category_name ?? "Tất cả sản phẩm"}</h2></div>
          <span className="result-count" aria-live="polite">{loading ? "Đang tải…" : `${pagination.total_items} tin đăng`}</span>
        </div>
        <div className="category-row explore-categories" aria-label="Lọc theo danh mục">
          <button type="button" className={`category-pill ${categoryId === undefined ? "is-selected" : ""}`} aria-pressed={categoryId === undefined} onClick={() => onCategoryChange(undefined)}>Tất cả</button>
          {categories.map((item, index) => <button type="button" key={item.category_id} className={`category-pill category-${index % 4} ${categoryId === item.category_id ? "is-selected" : ""}`} aria-pressed={categoryId === item.category_id} onClick={() => onCategoryChange(item.category_id)}><span aria-hidden="true">{["▦", "⌁", "⌨", "✦"][index % 4]}</span>{item.category_name}</button>)}
        </div>
        {(query || categoryId !== undefined) && <button type="button" className="text-button explore-clear" onClick={onClearFilters}>Xóa bộ lọc</button>}
      </div>

      {loading ? <div className="explore-loading" role="status">Đang tải sản phẩm…</div> : products.length > 0 ? <div className="product-grid">{products.map((product) => <ProductCard key={product.product_id} product={product} onView={() => onViewProduct(product)} />)}</div> : <EmptyState title="Chưa có sản phẩm phù hợp" description="Hãy thử từ khóa khác hoặc chọn một danh mục khác." />}

      {!loading && pagination.total_pages > 1 && <nav className="pagination" aria-label="Phân trang sản phẩm">
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))}>← Trước</button>
        <span>Trang {pagination.current_page} / {pagination.total_pages}</span>
        <button type="button" disabled={page >= pagination.total_pages} onClick={() => onPageChange(Math.min(pagination.total_pages, page + 1))}>Sau →</button>
      </nav>}
    </section>
  </main>;
}
