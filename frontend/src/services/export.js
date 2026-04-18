/** Trigger a browser download of `content` as a file. */
function downloadFile(filename, content, mime = "text/plain") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Export verdicts array as JSON. */
export function exportVerdictsJSON(verdicts) {
  downloadFile(
    "dead-code-verdicts.json",
    JSON.stringify(verdicts, null, 2),
    "application/json"
  );
}

/** Export verdicts array as CSV. */
export function exportVerdictsCSV(verdicts) {
  const header = "file,function,line_start,line_end,suspect_type,verdict,confidence,reason,author_context";
  const rows = verdicts.map((v) => {
    const s = v.suspect;
    const escape = (val) => `"${String(val ?? "").replace(/"/g, '""')}"`;
    return [
      escape(s.file),
      escape(s.name),
      s.line_start,
      s.line_end,
      escape(s.suspect_type),
      escape(v.verdict),
      v.confidence,
      escape(v.reason),
      escape(v.author_context),
    ].join(",");
  });
  downloadFile("dead-code-verdicts.csv", [header, ...rows].join("\n"), "text/csv");
}

/** Export call graph as JSON. */
export function exportCallGraphJSON(graph) {
  downloadFile(
    "call-graph.json",
    JSON.stringify(graph, null, 2),
    "application/json"
  );
}

/** Export call graph as CSV. */
export function exportCallGraphCSV(graph) {
  const header = "function,calls";
  const rows = Object.entries(graph)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([fn, callees]) => {
      const escape = (val) => `"${String(val).replace(/"/g, '""')}"`;
      return `${escape(fn)},${escape(callees.join("; "))}`;
    });
  downloadFile("call-graph.csv", [header, ...rows].join("\n"), "text/csv");
}
