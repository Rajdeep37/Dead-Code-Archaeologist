"""FastAPI entry point.

Run with:
    uvicorn app.main:app --reload
"""

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.cache import VerdictCache
from app.dead_code_detector import DeadCodeDetector
from app.git_explorer import GitExplorer
from app.llm_agent import LLMAgent, build_evidence, evidence_is_oversized
from app.models import BlameEntry, CommitInfo, SuspectFunction, Verdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dead Code Archaeologist API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


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
    """Return all commits, newest first. Optionally filter by file."""
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


@app.get("/verdicts")
async def verdicts_stream(
    repo_path: str = Query(..., description="Absolute path to the local git repository"),
):
    """Stream LLM verdicts for all suspects as Server-Sent Events (one JSON Verdict per event)."""
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
    total = len(suspects)
    repo_sha = explorer.repo.head.commit.hexsha

    cache_dir = str(explorer.root / ".verdicts_cache")
    cache = VerdictCache(cache_dir)
    agent = LLMAgent()

    logger.info("Starting analysis: %d suspects in %s", total, explorer.root)

    try:
        yield f"event: start\ndata: {json.dumps({'total': total})}\n\n"

        for i, suspect in enumerate(suspects):
            key = cache.make_key(repo_sha, suspect.file, suspect.name)

            # Cache hit — serve instantly
            verdict = cache.get(key)
            if verdict is not None:
                logger.info("[%d/%d] cache hit: %s", i + 1, total, suspect.name)
                yield f"event: verdict\ndata: {verdict.model_dump_json()}\n\n"
                continue

            logger.info(
                "[%d/%d] judging: %s (%s)", i + 1, total, suspect.name, suspect.file
            )
            try:
                bundle = build_evidence(suspect, explorer)

                if evidence_is_oversized(bundle):
                    logger.warning(
                        "[%d/%d] SKIPPED (oversized evidence): %s",
                        i + 1, total, suspect.name,
                    )
                    skip_verdict = Verdict(
                        suspect=suspect,
                        verdict="investigate",
                        confidence=0,
                        reason="Skipped: evidence too large for LLM context window. Review manually.",
                        author_context="",
                    )
                    cache.set(key, skip_verdict)
                    yield f"event: verdict\ndata: {skip_verdict.model_dump_json()}\n\n"
                    continue

                judge_task = asyncio.create_task(agent.judge(bundle))

                try:
                    while not judge_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(judge_task), timeout=15.0)
                        except asyncio.TimeoutError:
                            logger.debug("  keepalive: still waiting for %s", suspect.name)
                            yield ": keepalive\n\n"
                except (asyncio.CancelledError, GeneratorExit):
                    judge_task.cancel()
                    raise

                verdict = judge_task.result()   # re-raises any exception from judge()
                cache.set(key, verdict)
                logger.info(
                    "  -> verdict=%s confidence=%d",
                    verdict.verdict, verdict.confidence,
                )
                yield f"event: verdict\ndata: {verdict.model_dump_json()}\n\n"

            except asyncio.TimeoutError:
                logger.warning("  -> TIMEOUT for %s", suspect.name)
                timeout_verdict = Verdict(
                    suspect=suspect,
                    verdict="investigate",
                    confidence=0,
                    reason="Skipped: LLM timed out. Review manually.",
                    author_context="",
                )
                cache.set(key, timeout_verdict)
                yield f"event: verdict\ndata: {timeout_verdict.model_dump_json()}\n\n"
            except Exception as exc:
                logger.error("  -> FAILED %s: %s", suspect.name, exc)
                error_data = json.dumps({
                    "suspect": suspect.name,
                    "file": suspect.file,
                    "error": str(exc),
                })
                yield f"event: error\ndata: {error_data}\n\n"

        logger.info("Analysis complete: %d suspects processed", total)
        yield "event: done\ndata: {}\n\n"
    finally:
        cache.close()
