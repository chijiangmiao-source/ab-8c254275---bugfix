"""Structured API errors.

Every client-facing error is rendered as::

    {
      "error": {
        "code": "VALUE_OUT_OF_RANGE",
        "message": "matrix[1][2] = 70000 is outside ...",
        "location": {"row": 1, "col": 2}
      }
    }

``location`` is ``None`` only when the problem is not tied to any specific
place in the payload (e.g. the body is not a JSON object at all).
"""

from __future__ import annotations

from typing import Any, Optional


class ApiError(Exception):
    """An error that is returned to the client as a structured JSON body."""

    def __init__(
        self,
        code: str,
        message: str,
        location: Optional[dict[str, Any]] = None,
        status_code: int = 422,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.location = location
        self.status_code = status_code

    def payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "location": self.location,
            }
        }
