export default function ProgressBanner({ done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="progress-banner">
      <span className="spinner" />
      <div className="progress-banner__bar">
        <div className="progress-banner__fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="progress-banner__text">
        {done} / {total} verdicts
      </span>
    </div>
  );
}
