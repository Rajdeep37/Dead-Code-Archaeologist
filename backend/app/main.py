"""FastAPI entry point.

Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

app = FastAPI(title="Dead Code Archaeologist API")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
