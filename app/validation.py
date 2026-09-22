"""Validation of incoming analysis requests.

The matrix must be a rectangular array of integers with both side lengths in
[2, 96] and every gray value in [0, 65535].  ``min_persistence`` must be an
integer in [0, 65535].  Every rejection carries a machine-readable code and,
whenever the problem is tied to a concrete matrix entry, the exact row/column
location so engineers can fix their upload without guessing.
"""

from __future__ import annotations

from typing import Any

from .errors import ApiError

MIN_SIDE = 2
MAX_SIDE = 96
MIN_GRAY = 0
MAX_GRAY = 65535


def _is_int(value: Any) -> bool:
    # JSON booleans are ints in Python; gray levels and thresholds must not be.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_payload(payload: Any) -> tuple[list[list[int]], int]:
    """Validate the raw request body, returning ``(matrix, min_persistence)``."""
    if not isinstance(payload, dict):
        raise ApiError(
            "INVALID_PAYLOAD",
            "Request body must be a JSON object with fields "
            "'matrix' and 'min_persistence'.",
            status_code=400,
        )
    if "matrix" not in payload:
        raise ApiError(
            "MISSING_FIELD",
            "Missing required field 'matrix'.",
            {"field": "matrix"},
        )
    if "min_persistence" not in payload:
        raise ApiError(
            "MISSING_FIELD",
            "Missing required field 'min_persistence'.",
            {"field": "min_persistence"},
        )
    matrix = _validate_matrix(payload["matrix"])
    min_persistence = _validate_min_persistence(payload["min_persistence"])
    return matrix, min_persistence


def _validate_matrix(matrix: Any) -> list[list[int]]:
    if not isinstance(matrix, list):
        raise ApiError(
            "INVALID_MATRIX",
            "'matrix' must be a JSON array of equally sized integer arrays, "
            f"got {type(matrix).__name__}.",
            {"field": "matrix"},
        )
    height = len(matrix)
    if not MIN_SIDE <= height <= MAX_SIDE:
        raise ApiError(
            "INVALID_DIMENSIONS",
            f"Matrix height {height} is outside the allowed range "
            f"[{MIN_SIDE}, {MAX_SIDE}].",
            {"height": height},
        )
    width: int | None = None
    for r, row in enumerate(matrix):
        if not isinstance(row, list):
            raise ApiError(
                "INVALID_ROW",
                f"Row {r} must be a JSON array of integers, "
                f"got {type(row).__name__}.",
                {"row": r},
            )
        if width is None:
            width = len(row)
            if not MIN_SIDE <= width <= MAX_SIDE:
                raise ApiError(
                    "INVALID_DIMENSIONS",
                    f"Matrix width {width} is outside the allowed range "
                    f"[{MIN_SIDE}, {MAX_SIDE}].",
                    {"row": r, "width": width},
                )
        elif len(row) != width:
            raise ApiError(
                "NON_RECTANGULAR",
                f"Row {r} has length {len(row)} but row 0 has length {width}; "
                "the matrix must be rectangular.",
                {"row": r, "expected": width, "actual": len(row)},
            )
        for c, value in enumerate(row):
            if not _is_int(value):
                raise ApiError(
                    "INVALID_VALUE_TYPE",
                    f"matrix[{r}][{c}] must be an integer gray level, "
                    f"got {value!r}.",
                    {"row": r, "col": c},
                )
            if not MIN_GRAY <= value <= MAX_GRAY:
                raise ApiError(
                    "VALUE_OUT_OF_RANGE",
                    f"matrix[{r}][{c}] = {value} is outside the allowed gray "
                    f"range [{MIN_GRAY}, {MAX_GRAY}].",
                    {"row": r, "col": c, "value": value},
                )
    return matrix


def _validate_min_persistence(value: Any) -> int:
    if not _is_int(value):
        raise ApiError(
            "INVALID_MIN_PERSISTENCE",
            f"'min_persistence' must be an integer, got {value!r}.",
            {"field": "min_persistence"},
        )
    if not MIN_GRAY <= value <= MAX_GRAY:
        raise ApiError(
            "MIN_PERSISTENCE_OUT_OF_RANGE",
            f"'min_persistence' = {value} is outside the allowed range "
            f"[{MIN_GRAY}, {MAX_GRAY}].",
            {"field": "min_persistence", "value": value},
        )
    return value
