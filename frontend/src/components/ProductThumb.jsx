const KNOWN = ["stationery", "furniture", "electronics"];

export default function ProductThumb({ category, size = 40 }) {
  const key = (category || "").toLowerCase().trim();
  const file = KNOWN.includes(key) ? key : "default";
  return <img className="product-thumb" src={`/images/product-${file}.svg`} alt={category || "Product"} width={size} height={size} loading="lazy" />;
}
