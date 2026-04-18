import { useParams, useNavigate } from "react-router-dom";
import { useAnalysis } from "../context/AnalysisContext";
import VerdictBadge from "../components/VerdictBadge";
import TypeBadge from "../components/TypeBadge";
import ConfidenceBar from "../components/ConfidenceBar";

export default function VerdictDetailPage() {
  const { file, name } = useParams();
  const navigate = useNavigate();
  const { findVerdict } = useAnalysis();

  const v = findVerdict(decodeURIComponent(file), name);

  if (!v) {
    return (
      <div className="blankslate">
        <div className="blankslate__heading">Verdict not found</div>
        <div className="blankslate__text">
          Go back and run an analysis first, then select a suspect.
        </div>
      </div>
    );
  }

  const s = v.suspect;

  return (
    <>
      <button className="back-link" onClick={() => navigate(-1)}>
        ← Back to results
      </button>

      <div className="verdict-detail">
        <div className="verdict-detail__header">
          <div className="verdict-detail__title">
            <code style={{ fontSize: "inherit" }}>{s.name}</code>
            <VerdictBadge verdict={v.verdict} />
          </div>
          <div className="verdict-detail__subtitle">
            {s.file} · Lines {s.line_start}–{s.line_end} ·{" "}
            <TypeBadge type={s.suspect_type} />
          </div>
        </div>

        <div className="verdict-detail__body">
          {/* Confidence */}
          <div className="verdict-section">
            <div className="verdict-section__label">Confidence</div>
            <div className="verdict-section__content">
              <ConfidenceBar confidence={v.confidence} verdict={v.verdict} />
            </div>
          </div>

          {/* Reason */}
          <div className="verdict-section">
            <div className="verdict-section__label">Reason</div>
            <div className="verdict-section__content">{v.reason}</div>
          </div>

          {/* Author context */}
          <div className="verdict-section">
            <div className="verdict-section__label">Author Context</div>
            <div className="verdict-section__content">
              {v.author_context || "No author context available."}
            </div>
          </div>

          {/* File location */}
          <div className="verdict-section">
            <div className="verdict-section__label">Location</div>
            <div className="code-block">
              {s.file}:{s.line_start}-{s.line_end}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
