import { useEffect, useState } from "react";
import type { ProductMedia } from "../types";

type ProductMediaGalleryProps = {
  media?: ProductMedia[];
  productId: number;
  productTitle: string;
  fallbackGlyph: string;
  mode: "card" | "detail" | "thumbnail";
};

export function ProductMediaGallery({
  media,
  productId,
  productTitle,
  fallbackGlyph,
  mode,
}: ProductMediaGalleryProps) {
  const orderedMedia = [...(media ?? [])].sort(
    (a, b) => a.sort_order - b.sort_order || a.media_id - b.media_id,
  );
  const mediaSignature = orderedMedia.map((item) => `${item.media_id}:${item.url}`).join("|");
  const [activeMediaId, setActiveMediaId] = useState<number | null>(null);
  const [failedMediaIds, setFailedMediaIds] = useState<Set<number>>(() => new Set());

  useEffect(() => {
    setActiveMediaId(null);
    setFailedMediaIds(new Set());
  }, [productId, mediaSignature]);

  const availableMedia = orderedMedia.filter((item) => !failedMediaIds.has(item.media_id));
  const preferredMedia = availableMedia.find((item) => item.is_cover) ?? availableMedia[0];
  const activeMedia =
    availableMedia.find((item) => item.media_id === activeMediaId) ?? preferredMedia;
  const activeIndex = activeMedia
    ? orderedMedia.findIndex((item) => item.media_id === activeMedia.media_id)
    : -1;

  const markAsFailed = (mediaId: number) => {
    setFailedMediaIds((current) => new Set(current).add(mediaId));
  };

  return (
    <div
      className={`product-media-gallery product-media-gallery--${mode}`}
      role="group"
      aria-label={`Ảnh sản phẩm: ${productTitle}`}
    >
      <div className="product-media-stage" aria-live="polite">
        {activeMedia ? (
          <img
            className="product-media-source"
            src={activeMedia.url}
            alt={activeMedia.alt_text?.trim() || `${productTitle} — ảnh ${activeIndex + 1}`}
            loading={mode === "detail" ? "eager" : "lazy"}
            decoding="async"
            onError={() => markAsFailed(activeMedia.media_id)}
          />
        ) : (
          <span className="image-glyph" aria-hidden="true">{fallbackGlyph}</span>
        )}
        {mode === "card" && orderedMedia.length > 1 && (
          <span className="product-media-count" aria-label={`${orderedMedia.length} ảnh sản phẩm`}>
            {orderedMedia.length} ảnh
          </span>
        )}
      </div>

      {mode === "detail" && orderedMedia.length > 1 && (
        <div className="product-media-thumbnails" role="group" aria-label="Chọn ảnh sản phẩm">
          {orderedMedia.map((item, index) => {
            const failed = failedMediaIds.has(item.media_id);
            const selected = activeMedia?.media_id === item.media_id;
            return (
              <button
                key={item.media_id}
                type="button"
                className="product-media-thumbnail"
                aria-label={failed ? `Ảnh ${index + 1} không tải được` : `Xem ảnh ${index + 1}`}
                aria-pressed={selected}
                disabled={failed}
                onClick={() => setActiveMediaId(item.media_id)}
              >
                {failed ? (
                  <span aria-hidden="true">—</span>
                ) : (
                  <img
                    src={item.url}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    onError={() => markAsFailed(item.media_id)}
                  />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
