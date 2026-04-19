import { createContext, useContext, useState, useRef, useCallback } from "react";
import { streamVerdicts, fetchCallGraph } from "../services/api";

const AnalysisContext = createContext(null);

export function AnalysisProvider({ children }) {
  const [repoPath, setRepoPath] = useState("");
  const [verdicts, setVerdicts] = useState([]);
  const [total, setTotal] = useState(0);
  const [streaming, setStreaming] = useState(false);
  const [errors, setErrors] = useState([]);
  const [callGraph, setCallGraph] = useState(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const sourceRef = useRef(null);

  const startAnalysis = useCallback(() => {
    const path = repoPath.trim();
    if (!path || streaming) return;

    setVerdicts([]);
    setErrors([]);
    setTotal(0);
    setCallGraph(null);
    setStreaming(true);

    setGraphLoading(true);
    fetchCallGraph(path)
      .then(setCallGraph)
      .catch(() => {}) // non-critical
      .finally(() => setGraphLoading(false));

    sourceRef.current = streamVerdicts(path, {
      onStart: ({ total: t }) => setTotal(t),
      onVerdict: (v) => setVerdicts((prev) => [...prev, v]),
      onError: (e) => setErrors((prev) => [...prev, e]),
      onDone: () => setStreaming(false),
    });

    sourceRef.current.onerror = () => {
      setStreaming(false);
      sourceRef.current?.close();
    };
  }, [repoPath, streaming]);

  /** Look up a verdict by file+name (used by detail page). */
  const findVerdict = useCallback(
    (file, name) => verdicts.find((v) => v.suspect.file === file && v.suspect.name === name),
    [verdicts]
  );

  return (
    <AnalysisContext.Provider
      value={{
        repoPath,
        setRepoPath,
        verdicts,
        total,
        streaming,
        errors,
        callGraph,
        graphLoading,
        startAnalysis,
        findVerdict,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error("useAnalysis must be inside AnalysisProvider");
  return ctx;
}
