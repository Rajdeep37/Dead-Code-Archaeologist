"""FastAPI entry point.

Run with:
    uvicorn app.main:app --reload
"""

import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.cache import VerdictCache
from app.dead_code_detector import DeadCodeDetector
from app.git_explorer import GitExplorer
from app.llm_agent import LLMAgent, build_evidence
from app.models import BlameEntry, CommitInfo, SuspectFunction, Verdict

app = FastAPI(title="Dead Code Archaeologist API")


# ------------------------------------------------------------------ #
# Health                                                               #
# ------------------------------------------------------------------ #

@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


# ------------------------------------------------------------------ #
# Git explorer endpoints                                               #
# ------------------------------------------------------------------ #

def _get_explorer(repo_path: str) -> GitExplorer:
    """Create a GitExplorer or raise a 400 with a clear message."""
    try:
        return GitExplorer(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/commits", response_model=list[CommitInfo])
def list_commits(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
    file_path: str | None = Query(None, description="Filter to commits that touched this file"),
):
    """Return all commits for the repository, newest first.

    Optionally filter to a single file with ``file_path``.
    """
    explorer = _get_explorer(repo_path)
    return explorer.get_all_commits(file_path=file_path)


@app.get("/blame", response_model=list[BlameEntry])
def blame_file(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
    file_path: str = Query(..., description="File to blame, relative to repository root"),
    rev: str = Query("HEAD", description="Git revision to blame against"),
):
    """Return a line-by-line blame for a file."""
    explorer = _get_explorer(repo_path)
    try:
        return explorer.get_file_blame(file_path, rev=rev)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/diff")
def commit_diff(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
    sha: str = Query(..., description="Full or short commit SHA"),
) -> dict[str, str]:
    """Return the full unified diff for a single commit."""
    explorer = _get_explorer(repo_path)
    try:
        return {"sha": sha, "diff": explorer.get_commit_diff(sha)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------ #
# Dead code analysis endpoints                                         #
# ------------------------------------------------------------------ #

def _get_detector(repo_path: str) -> DeadCodeDetector:
    """Create a DeadCodeDetector or raise a 400 with a clear message."""
    try:
        return DeadCodeDetector(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/analyze", response_model=list[SuspectFunction])
def analyze_repo(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
):
    """Find suspect dead-code functions in the repository."""
    detector = _get_detector(repo_path)
    return detector.find_suspects()


@app.get("/call-graph")
def call_graph(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
) -> dict[str, list[str]]:
    """Return the call graph as an adjacency dict."""
    detector = _get_detector(repo_path)
    return detector.get_call_graph_dict()


# ------------------------------------------------------------------ #
# LLM verdict endpoints (SSE streaming)                                #
# ------------------------------------------------------------------ #

@app.get("/verdicts")
async def verdicts_stream(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
):
    """Stream LLM verdicts for all suspects as Server-Sent Events.

    Each event is a JSON-encoded Verdict. Cached verdicts are served
    instantly; uncached ones are judged by the LLM on the fly.
    """
    try:
        explorer = GitExplorer(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        detector = DeadCodeDetector(repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return StreamingResponse(
        _verdict_generator(explorer, detector),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _verdict_generator(explorer: GitExplorer, detector: DeadCodeDetector):
    """Async generator that yields SSE events — one per suspect."""
    suspects = detector.find_suspects()
    repo_sha = explorer.repo.head.commit.hexsha

    cache_dir = str(explorer.root / ".verdicts_cache")
    cache = VerdictCache(cache_dir)
    agent = LLMAgent()

    try:
        # Send an initial event with the total count
        yield f"event: start\ndata: {json.dumps({'total': len(suspects)})}\n\n"

        for i, suspect in enumerate(suspects):
            key = cache.make_key(repo_sha, suspect.file, suspect.name)

            # Check cache first
            verdict = cache.get(key)
            if verdict is not None:
                payload = verdict.model_dump_json()
                yield f"event: verdict\ndata: {payload}\n\n"
                continue

            # LLM call
            try:
                bundle = build_evidence(suspect, explorer)
                verdict = await agent.judge(bundle)
                cache.set(key, verdict)
                payload = verdict.model_dump_json()
                yield f"event: verdict\ndata: {payload}\n\n"
            except Exception as exc:
                error_data = json.dumps({
                    "suspect": suspect.name,
                    "file": suspect.file,
                    "error": str(exc),
                })
                yield f"event: error\ndata: {error_data}\n\n"

        yield "event: done\ndata: {}\n\n"
    finally:
        cache.close()
