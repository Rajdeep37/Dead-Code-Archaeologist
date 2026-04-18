import { useState } from "react";
import { fetchCallGraph } from "../services/api";

export default function CallGraphPage() {
  const [repoPath, setRepoPath] = useState("");
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const load = async () => {
    if (!repoPath.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchCallGraph(repoPath.trim());
      setGraph(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") load();
  };

  const entries = graph
    ? Object.entries(graph)
        .filter(
          ([node, callees]) =>
            !search ||
            node.toLowerCase().includes(search.toLowerCase()) ||
            callees.some((c) => c.toLowerCase().includes(search.toLowerCase()))
        )
        .sort(([a], [b]) => a.localeCompare(b))
    : [];

  return (
    <>
      <div className="repo-header">
        <div className="repo-header__title">
          <strong>Dead Code Archaeologist</strong> / call-graph
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
            onClick={load}
            disabled={loading || !repoPath.trim()}
          >
            {loading ? (
              <>
                <span className="spinner" /> Loading…
              </>
            ) : (
              "📊 Load Graph"
            )}
          </button>
        </div>
      </div>

      {error && <div className="flash flash-error">{error}</div>}

      {graph && (
        <>
          <div className="repo-input-row" style={{ marginBottom: 16 }}>
            <input
              className="repo-input"
              placeholder="Search functions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ fontFamily: "var(--font-sans)" }}
            />
          </div>

          <div className="graph-table-wrapper">
            <table className="graph-table">
              <thead>
                <tr>
                  <th style={{ width: "40%" }}>Function</th>
                  <th>Calls →</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(([node, callees]) => (
                  <tr key={node}>
                    <td>{node}</td>
                    <td>
                      {callees.length > 0
                        ? callees.join(", ")
                        : <span style={{ color: "var(--color-fg-subtle)" }}>— (leaf)</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 12, fontSize: 13, color: "var(--color-fg-muted)" }}>
            {entries.length} of {Object.keys(graph).length} functions shown
          </div>
        </>
      )}

      {!graph && !loading && (
        <div className="blankslate">
          <div className="blankslate__icon">🕸️</div>
          <div className="blankslate__heading">No call graph loaded</div>
          <div className="blankslate__text">
            Enter a repo path and click Load Graph to view the function call
            relationships.
          </div>
        </div>
      )}
    </>
  );
}
