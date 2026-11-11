import type { Category } from "../types";

type MarketPageProps = {
  categories: Category[];
  query: string;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onExplore: (categoryId?: number) => void;
};

export function MarketPage({ categories, query, onQueryChange, onSearch, onExplore }: MarketPageProps) {
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
      <div className="section-heading"><div><p className="eyebrow">Bắt đầu từ đâu?</p><h2>Khám phá theo danh mục</h2></div><button className="text-button" onClick={() => onExplore()}>Xem tất cả <span>↗</span></button></div>
      <div className="category-row">{categories.map((item, index) => <button className={`category-pill category-${index % 4}`} key={item.category_id} onClick={() => onExplore(item.category_id)}><span>{["▦", "⌁", "⌨", "✦"][index % 4]}</span>{item.category_name}</button>)}</div>
    </section>
    <section className="wide-banner"><div><p className="eyebrow">Dành cho bạn</p><h2>Một vòng quanh chợ,<br />một món đồ vừa ý.</h2><button className="dark-button" onClick={() => onExplore()}>Xem sản phẩm <span>↗</span></button></div><div className="banner-shape">✳</div></section>
  </main>;
}
