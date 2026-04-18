export default function VerdictBadge({ verdict }) {
  const label = verdict.charAt(0).toUpperCase() + verdict.slice(1);
  return <span className={`badge badge-${verdict}`}>{label}</span>;
}
