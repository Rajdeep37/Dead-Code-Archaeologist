export default function TypeBadge({ type }) {
  const labels = {
    uncalled: "Uncalled",
    comment_smell: "Comment smell",
  };
  return (
    <span className={`badge badge-${type}`}>{labels[type] || type}</span>
  );
}
