import { Trash2, CheckCircle2, Search } from "lucide-react";
import VerdictBadge from "./VerdictBadge";
import TypeBadge from "./TypeBadge";
import ConfidenceBar from "./ConfidenceBar";

const VERDICT_ICONS = {
  delete: <Trash2 size={16} color="var(--color-danger-fg)" />,
  keep: <CheckCircle2 size={16} color="var(--color-success-fg)" />,
  investigate: <Search size={16} color="var(--color-attention-fg)" />,
};

/** A single row in the suspect list — GitHub-Issues style. */
export default function SuspectRow({ verdict, onClick }) {
  const s = verdict.suspect;
  const icon = VERDICT_ICONS[verdict.verdict] || VERDICT_ICONS.investigate;

  return (
    <div className="suspect-item" onClick={onClick} role="button" tabIndex={0}>
      <div className="suspect-item__icon">{icon}</div>
      <div className="suspect-item__body">
        <div className="suspect-item__title">
          <code>{s.name}</code>
        </div>
        <div className="suspect-item__file">{s.file}:{s.line_start}</div>
        <div className="suspect-item__meta">
          <VerdictBadge verdict={verdict.verdict} />
          <TypeBadge type={s.suspect_type} />
          <ConfidenceBar confidence={verdict.confidence} verdict={verdict.verdict} />
        </div>
      </div>
    </div>
  );
}
