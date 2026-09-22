"""Analysis pipeline: filtration -> GF(2) reduction -> verified barcode payload.

Besides computing the barcode, every reported bar is re-checked against the
topological evidence the API promises:

* the birth cycle is an even-degree closed chain (every vertex of the grid is
  incident to an even number of its edges);
* the birth edge is the unique youngest edge of the cycle, so the cycle
  exists at the birth threshold and at no earlier one.

The remaining guarantee — the reported square triggers the death of the class
exactly at the death threshold — follows from the reduction itself and is
exercised independently by the test-suite for every computed bar.
"""

from __future__ import annotations

from typing import Any

from .errors import ApiError
from .filtration import H_EDGE, Cell, Filtration
from .persistence import Bar, compute_h1_bars


def analyze(matrix: list[list[int]], min_persistence: int) -> dict[str, Any]:
    """Compute the 1-D barcode of ``matrix`` and build the response payload."""
    filtration = Filtration(matrix)
    bars = compute_h1_bars(filtration)
    for bar in bars:
        _check_bar(bar)

    kept = [
        bar
        for bar in bars
        if bar.death_square.value > bar.birth_edge.value
        and bar.persistence >= min_persistence
    ]
    # Deterministic ranking: persistence descending, then birth value, then
    # the filtration order of the birth edge (unique per bar) and death square.
    kept.sort(
        key=lambda b: (
            -b.persistence,
            b.birth_edge.value,
            b.birth_edge.order,
            b.death_square.order,
        )
    )

    return {
        "matrix": {"height": filtration.height, "width": filtration.width},
        "min_persistence": min_persistence,
        "bar_count": len(kept),
        "bars": [_bar_payload(bar) for bar in kept],
    }


def edge_endpoints(cell: Cell) -> tuple[tuple[int, int], tuple[int, int]]:
    """The two vertex positions ``((r1, c1), (r2, c2))`` of an edge cell."""
    if cell.kind == H_EDGE:
        return (cell.row, cell.col), (cell.row, cell.col + 1)
    return (cell.row, cell.col), (cell.row + 1, cell.col)


def _check_bar(bar: Bar) -> None:
    """Defensive re-verification of a computed bar (should never fail)."""
    cycle = bar.cycle_edges
    if not cycle or cycle[-1] != bar.birth_edge:
        raise ApiError(
            "INTERNAL_INVARIANT",
            "Birth edge is not the youngest edge of its birth cycle.",
            status_code=500,
        )
    parity: dict[tuple[int, int], int] = {}
    for edge in cycle:
        for vertex in edge_endpoints(edge):
            parity[vertex] = parity.get(vertex, 0) ^ 1
    if any(parity.values()):
        raise ApiError(
            "INTERNAL_INVARIANT",
            "Birth cycle is not an even-degree closed chain.",
            status_code=500,
        )


def _edge_payload(cell: Cell) -> dict[str, Any]:
    (r1, c1), (r2, c2) = edge_endpoints(cell)
    return {
        "kind": "horizontal" if cell.kind == H_EDGE else "vertical",
        "row": cell.row,
        "col": cell.col,
        "endpoints": [[r1, c1], [r2, c2]],
        "value": cell.value,
        "order": cell.order,
    }


def _square_payload(cell: Cell) -> dict[str, Any]:
    r, c = cell.row, cell.col
    return {
        "row": r,
        "col": c,
        "corners": [[r, c], [r, c + 1], [r + 1, c], [r + 1, c + 1]],
        "value": cell.value,
        "order": cell.order,
    }


def _bar_payload(bar: Bar) -> dict[str, Any]:
    return {
        "birth_value": bar.birth_edge.value,
        "death_value": bar.death_square.value,
        "persistence": bar.persistence,
        "birth_edge": _edge_payload(bar.birth_edge),
        "death_square": _square_payload(bar.death_square),
        "birth_cycle": {
            "edge_count": len(bar.cycle_edges),
            "edges": [_edge_payload(edge) for edge in bar.cycle_edges],
        },
    }
