export default function Badge({ value }) {
  const cls = "badge-" + String(value).toLowerCase().replace(/\s+/g, "-");
  return <span className={`badge ${cls}`}>{value}</span>;
}
