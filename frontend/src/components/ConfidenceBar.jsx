const VERDICT_COLORS = {
  delete: "var(--color-danger-fg)",
  investigate: "var(--color-attention-fg)",
  keep: "var(--color-success-fg)",
};

export default function ConfidenceBar({ confidence, verdict }) {
  const color = VERDICT_COLORS[verdict] || "var(--color-accent-fg)";

  return (
    <div className="confidence-bar">
      <div className="confidence-bar__track">
        <div
          className="confidence-bar__fill"
          style={{ width: `${confidence}%`, background: color }}
        />
      </div>
      <span className="confidence-bar__label" style={{ color }}>
        {confidence}%
      </span>
    </div>
  );
}
