export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** GET JSON from the backend. */
async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

/** Fetch suspects list (static analysis only, no LLM). */
export function fetchSuspects(repoPath) {
  return fetchJSON(`/analyze?repo_path=${encodeURIComponent(repoPath)}`);
}

/** Fetch the call graph adjacency dict. */
export function fetchCallGraph(repoPath) {
  return fetchJSON(`/call-graph?repo_path=${encodeURIComponent(repoPath)}`);
}

/**
 * Stream LLM verdicts via SSE.
 * Returns an EventSource-like interface; call `close()` to stop.
 *
 * @param {string} repoPath
 * @param {object} handlers - { onStart, onVerdict, onError, onDone }
 */
export function streamVerdicts(repoPath, { onStart, onVerdict, onError, onDone }) {
  const url = `${API_BASE}/verdicts?repo_path=${encodeURIComponent(repoPath)}`;
  const source = new EventSource(url);

  source.addEventListener("start", (e) => {
    onStart?.(JSON.parse(e.data));
  });

  source.addEventListener("verdict", (e) => {
    onVerdict?.(JSON.parse(e.data));
  });

  source.addEventListener("error", (e) => {
    if (e.data) {
      onError?.(JSON.parse(e.data));
    }
  });

  source.addEventListener("done", () => {
    onDone?.();
    source.close();
  });

  return source;
}