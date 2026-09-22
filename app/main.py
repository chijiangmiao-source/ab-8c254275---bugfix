"""HTTP API for the H1 persistence analysis service (backend only)."""

from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .errors import ApiError
from .service import analyze
from .validation import validate_payload

app = FastAPI(
    title="Rock-Core CT H1 Persistence Service",
    version=__version__,
    description=(
        "Computes the 1-dimensional persistence barcode of a grayscale "
        "core-CT slice under the lower-star cubical filtration, using an "
        "in-house GF(2) sparse boundary reduction."
    ),
)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.payload())


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe used by Docker and Compose healthchecks."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "rock-core-ct-h1-persistence",
        "version": __version__,
        "endpoints": {
            "health": "GET /health",
            "analyze": "POST /api/v1/barcode",
            "docs": "GET /docs",
        },
    }


@app.post("/api/v1/barcode")
async def barcode(request: Request) -> dict[str, object]:
    """Analyze one grayscale matrix and return its 1-D persistence barcode."""
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise ApiError(
            "INVALID_JSON",
            "Request body is not valid JSON.",
            status_code=400,
        )
    matrix, min_persistence = validate_payload(payload)
    return analyze(matrix, min_persistence)
