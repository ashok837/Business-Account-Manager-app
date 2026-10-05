export default function EmptyState({ title = "Nothing here yet", hint }) {
  return (
    <div className="empty-art">
      <img src="/images/empty-state.svg" alt="" />
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}
