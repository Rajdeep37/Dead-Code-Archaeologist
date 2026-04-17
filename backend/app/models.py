"""Pydantic models shared across the pipeline."""

from pydantic import BaseModel


class CommitInfo(BaseModel):
    sha: str
    author: str
    date: str
    message: str


class SuspectFunction(BaseModel):
    name: str
    file: str
    line_start: int
    line_end: int


class Verdict(BaseModel):
    suspect: SuspectFunction
    verdict: str          # "delete" | "investigate" | "keep"
    confidence: int       # 0–100
    reason: str
    author_context: str
