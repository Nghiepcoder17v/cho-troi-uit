import type { Category, Condition, Pagination, Product, ProductSort } from "../types";
import { ProductCard } from "../components/ProductCard";
import { EmptyState } from "../components/primitives";

type ExplorePageProps = {
  categories: Category[];
  products: Product[];
  page: number;
  pagination: Pagination;
  query: string;
  categoryId?: number;
  condition: Condition | "";
  minPrice: string;
  maxPrice: string;
  sort: ProductSort;
  hasActiveFilters: boolean;
  loading: boolean;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onCategoryChange: (value?: number) => void;
  onConditionChange: (value: Condition | "") => void;
  onMinPriceChange: (value: string) => void;
  onMaxPriceChange: (value: string) => void;
  onSortChange: (value: ProductSort) => void;
  onApplyFilters: () => void;
  onClearFilters: () => void;
  onPageChange: (value: number) => void;
  onViewProduct: (product: Product) => void;
  favoriteIds: ReadonlySet<number>;
  pendingFavoriteIds: ReadonlySet<number>;
  onToggleFavorite: (productId: number) => void;
};

export function ExplorePage({
  categories, products, page, pagination, query, categoryId, condition,
  minPrice, maxPrice, sort, hasActiveFilters, loading, onQueryChange, onSearch, onCategoryChange,
  onConditionChange, onMinPriceChange, onMaxPriceChange, onSortChange,
  onApplyFilters, onClearFilters, onPageChange, onViewProduct,
  favoriteIds, pendingFavoriteIds, onToggleFavorite,
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

        <div className="explore-filter-panel" role="group" aria-label="Bộ lọc nâng cao">
          <label className="explore-filter-field">
            <span>Tình trạng</span>
            <select value={condition} onChange={(event) => onConditionChange(event.target.value as Condition | "")}>
              <option value="">Tất cả tình trạng</option>
              <option value="Brand New">Mới 100%</option>
              <option value="Like New">Như mới</option>
              <option value="Good">Tốt</option>
              <option value="Fair">Đã qua sử dụng</option>
            </select>
          </label>
          <label className="explore-filter-field">
            <span>Giá từ (₫)</span>
            <input type="number" min="0" max="99999999.99" step="0.01" inputMode="decimal" value={minPrice} onChange={(event) => onMinPriceChange(event.target.value)} placeholder="Không giới hạn" />
          </label>
          <label className="explore-filter-field">
            <span>Đến (₫)</span>
            <input type="number" min="0" max="99999999.99" step="0.01" inputMode="decimal" value={maxPrice} onChange={(event) => onMaxPriceChange(event.target.value)} placeholder="Không giới hạn" />
          </label>
          <label className="explore-filter-field">
            <span>Sắp xếp</span>
            <select value={sort} onChange={(event) => onSortChange(event.target.value as ProductSort)}>
              <option value="newest">Mới đăng trước</option>
              <option value="price_asc">Giá thấp đến cao</option>
              <option value="price_desc">Giá cao đến thấp</option>
            </select>
          </label>
          <button type="button" className="explore-apply" disabled={loading} onClick={onApplyFilters}>Áp dụng bộ lọc</button>
        </div>
        {hasActiveFilters && <button type="button" className="text-button explore-clear" onClick={onClearFilters}>Xóa bộ lọc</button>}
      </div>

      {loading ? <div className="explore-loading" role="status">Đang tải sản phẩm…</div> : products.length > 0 ? <div className="product-grid">{products.map((product) => <ProductCard
        key={product.product_id}
        product={product}
        onView={() => onViewProduct(product)}
        isFavorite={favoriteIds.has(product.product_id)}
        favoriteBusy={pendingFavoriteIds.has(product.product_id)}
        onToggleFavorite={() => onToggleFavorite(product.product_id)}
      />)}</div> : <EmptyState title="Chưa có sản phẩm phù hợp" description="Hãy thử thay đổi từ khóa hoặc bộ lọc để tìm thêm sản phẩm." />}

      {!loading && pagination.total_pages > 1 && <nav className="pagination" aria-label="Phân trang sản phẩm">
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))}>← Trước</button>
        <span>Trang {pagination.current_page} / {pagination.total_pages}</span>
        <button type="button" disabled={page >= pagination.total_pages} onClick={() => onPageChange(Math.min(pagination.total_pages, page + 1))}>Sau →</button>
      </nav>}
    </section>
  </main>;
}
