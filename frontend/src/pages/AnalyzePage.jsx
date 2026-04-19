import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search as SearchIcon, FlaskConical, Download, GitFork, AlertTriangle, Skull } from "lucide-react";
import { useAnalysis } from "../context/AnalysisContext";
import SuspectRow from "../components/SuspectRow";
import ProgressBanner from "../components/ProgressBanner";
import {
  exportVerdictsJSON,
  exportVerdictsCSV,
  exportCallGraphJSON,
  exportCallGraphCSV,
} from "../services/export";

export default function AnalyzePage() {
  const {
    repoPath,
    setRepoPath,
    verdicts,
    total,
    streaming,
    errors,
    callGraph,
    graphLoading,
    startAnalysis,
  } = useAnalysis();

  const [filter, setFilter] = useState("all");
  const [graphSearch, setGraphSearch] = useState("");
  const navigate = useNavigate();

  // Reset search whenever a fresh call graph arrives
  useEffect(() => {
    if (callGraph) setGraphSearch("");
  }, [callGraph]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter") startAnalysis();
  };

  const filtered =
    filter === "all"
      ? verdicts
      : verdicts.filter((v) => v.verdict === filter);

  const counts = {
    all: verdicts.length,
    delete: verdicts.filter((v) => v.verdict === "delete").length,
    investigate: verdicts.filter((v) => v.verdict === "investigate").length,
    keep: verdicts.filter((v) => v.verdict === "keep").length,
  };

  // Search only the function-name portion (after "::") so "main" won't match
  // every function defined in main.py
  const graphEntries = useMemo(() => {
    if (!callGraph) return [];
    const term = graphSearch.toLowerCase();
    return Object.entries(callGraph)
      .filter(([node, callees]) => {
        if (!term) return true;
        const funcName = node.includes("::") ? node.split("::").pop() : node;
        if (funcName.toLowerCase().includes(term)) return true;
        return callees.some((c) => {
          const calleeName = c.includes("::") ? c.split("::").pop() : c;
          return calleeName.toLowerCase().includes(term);
        });
      })
      .sort(([a], [b]) => a.localeCompare(b));
  }, [callGraph, graphSearch]);

  return (
    <>
      <div className="repo-header">
        <div className="repo-header__title">
          <strong>Dead Code Archaeologist</strong> / analyze
        </div>
        <div className="repo-input-row">
          <input
            className="repo-input"
            placeholder="Enter absolute path to a git repository..."
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            className="btn btn-primary"
            onClick={startAnalysis}
            disabled={streaming || !repoPath.trim()}
          >
            {streaming ? (
              <>
                <span className="spinner" /> Analyzing…
              </>
            ) : (
              <>
                <FlaskConical size={14} /> Analyze
              </>
            )}
          </button>
        </div>
      </div>

      {streaming && <ProgressBanner done={verdicts.length} total={total} />}

      {errors.map((err, i) => (
        <div key={i} className="flash flash-error">
          <AlertTriangle size={14} /> Failed to judge{" "}
          <strong>{err.suspect}</strong> in {err.file}: {err.error}
        </div>
      ))}


      {verdicts.length > 0 && (
        <>
          <div className="export-toolbar">
            <Download size={14} className="export-toolbar__icon" />
            <span className="export-toolbar__label">Export verdicts:</span>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => exportVerdictsJSON(verdicts)}
            >
              JSON
            </button>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => exportVerdictsCSV(verdicts)}
            >
              CSV
            </button>
          </div>

          <div className="tab-nav">
            {["all", "delete", "investigate", "keep"].map((f) => (
              <button
                key={f}
                className={`tab-nav__item${
                  filter === f ? " tab-nav__item--active" : ""
                }`}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
                <span className="tab-nav__count">{counts[f]}</span>
              </button>
            ))}
          </div>

          <div className="suspect-list">
            <div className="suspect-list__header">
              {filtered.length} suspect{filtered.length !== 1 ? "s" : ""}
            </div>
            {filtered.map((v) => (
              <SuspectRow
                key={`${v.suspect.file}::${v.suspect.name}`}
                verdict={v}
                onClick={() =>
                  navigate(
                    `/verdict/${encodeURIComponent(v.suspect.file)}/${
                      v.suspect.name
                    }`
                  )
                }
              />
            ))}
          </div>
        </>
      )}


      {(callGraph || graphLoading) && (
        <div style={{ marginTop: 32 }}>
          <div className="section-heading">
            <h3 className="section-heading__title">
              <GitFork size={16} /> Call Graph
            </h3>
            {callGraph && (
              <div className="export-toolbar" style={{ marginBottom: 0 }}>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => exportCallGraphJSON(callGraph)}
                >
                  JSON
                </button>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => exportCallGraphCSV(callGraph)}
                >
                  CSV
                </button>
              </div>
            )}
          </div>

          {graphLoading && (
            <div style={{ padding: 16, color: "var(--color-fg-muted)" }}>
              <span className="spinner" /> Loading call graph…
            </div>
          )}

          {callGraph && (
            <>
              <div className="repo-input-row" style={{ marginBottom: 12 }}>
                <input
                  className="repo-input"
                  placeholder="Search functions..."
                  value={graphSearch}
                  onChange={(e) => setGraphSearch(e.target.value)}
                  style={{ fontFamily: "var(--font-sans)" }}
                />
              </div>
              <div className="graph-table-wrapper">
                <table className="graph-table">
                  <thead>
                    <tr>
                      <th style={{ width: "35%" }}>Function</th>
                      <th>Calls</th>
                    </tr>
                  </thead>
                  <tbody>
                    {graphEntries.map(([node, callees]) => (
                      <tr key={node}>
                        <td>{node}</td>
                        <td>
                          {callees.length > 0 ? (
                            callees.map((c, i) => (
                              <span key={c}>
                                {i > 0 && ", "}
                                <span className="graph-table__callee">{c}</span>
                              </span>
                            ))
                          ) : (
                            <span className="graph-table__leaf">no outgoing calls</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 8, fontSize: 13, color: "var(--color-fg-muted)" }}>
                {graphEntries.length} of {Object.keys(callGraph).length} functions shown
              </div>
            </>
          )}
        </div>
      )}

      {!streaming && verdicts.length === 0 && repoPath === "" && (
        <div className="blankslate">
          <div className="blankslate__icon">
            <Skull size={40} />
          </div>
          <div className="blankslate__heading">No repository analyzed yet</div>
          <div className="blankslate__text">
            Enter a path to a local git repository above and click Analyze to
            find dead code and get LLM-powered verdicts.
          </div>
        </div>
      )}
    </>
  );
}
