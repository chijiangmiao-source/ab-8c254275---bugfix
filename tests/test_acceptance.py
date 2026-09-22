"""End-to-end acceptance tests through the public HTTP interface.

These tests post real matrices to ``POST /api/v1/barcode`` (via the ASGI
HTTP client, or against a live server when ``BARCODE_BASE_URL`` is set) and
verify:

* HTTP status, bar count, birth/death values and the documented ordering;
* the whole barcode against an independent GF(2) rank ground truth
  (``tests.helpers.expected_bar_orders``);
* every reported birth cycle with an *independent* re-computation that builds
  its own cubical-cell model straight from the raw matrix (it never imports
  ``app.filtration`` / ``app.persistence``):
    1. at the birth threshold every vertex has even degree in the cycle;
    2. the cycle exists at no earlier threshold (its birth edge is the unique
       youngest edge, and no edge exceeds the birth value);
    3. below the reported death square the cycle is not the boundary of any
       square combination, and once that square is added it is exactly a
       boundary (the witnessing 2-chain contains the death square).

``GET /health`` is covered as well.
"""

from __future__ import annotations

import os

from app.filtration import Filtration
from tests.gf2 import solve
from tests.helpers import expected_bar_orders

try:  # exercised against a live container when BARCODE_BASE_URL is set
    import httpx
except ImportError:  # pragma: no cover - httpx is in requirements-dev
    httpx = None

from fastapi.testclient import TestClient

from app.main import app

H_KIND, V_KIND = 1, 2
KIND_FROM_WIRE = {"horizontal": H_KIND, "vertical": V_KIND}

TARGET_MATRIX = [
    [7, 7, 2, 9, 5],
    [5, 5, 6, 3, 5],
    [7, 8, 6, 7, 4],
    [1, 1, 3, 4, 3],
]
SINGLE_HOLE = [
    [0, 0, 0],
    [0, 9, 0],
    [0, 0, 0],
]
# Two equally high peaks on a constant low plateau: many cells share the
# same filtration value, so tie-breaking and interleaved pairing matter.
TWO_EQUAL_HOLES = [
    [1, 1, 1, 1, 1],
    [1, 5, 1, 5, 1],
    [1, 1, 1, 1, 1],
]
# Plateau ring around a 2x2 bright core: large blocks of equal-valued cells.
PLATEAU_RING = [
    [3, 3, 3, 3, 3, 3],
    [3, 0, 0, 0, 0, 3],
    [3, 0, 5, 5, 0, 3],
    [3, 0, 5, 5, 0, 3],
    [3, 0, 0, 0, 0, 3],
    [3, 3, 3, 3, 3, 3],
]
CONSTANT = [[7] * 5 for _ in range(4)]


class HttpSession:
    """Minimal GET/POST shim over either the ASGI app or a live server."""

    def __init__(self) -> None:
        base_url = os.environ.get("BARCODE_BASE_URL")
        if base_url:
            assert httpx is not None, "httpx is required to use BARCODE_BASE_URL"
            self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=30)
            self._live = True
        else:
            self._client = TestClient(app)
            self._live = False

    def get(self, path: str):
        return self._client.get(path)

    def post(self, path: str, payload: dict):
        return self._client.post(path, json=payload)

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Independent cubical-complex model, rebuilt solely from the raw matrix and
# the documented filtration rules (value, then kind, then row, then col).
# ---------------------------------------------------------------------------


def independent_complex(matrix: list[list[int]]):
    """Return (orders, edge_values, square_boundaries) keyed by coordinates.

    * orders: {(kind, row, col): filtration order}
    * edge_values: {edge key: value}
    * squares: sorted list of (order, row, col, {boundary edge keys})
    """
    height, width = len(matrix), len(matrix[0])
    raw: list[tuple[int, int, int, int]] = []
    for r in range(height):
        for c in range(width):
            raw.append((matrix[r][c], 0, r, c))
    for r in range(height):
        for c in range(width - 1):
            raw.append((max(matrix[r][c], matrix[r][c + 1]), H_KIND, r, c))
    for r in range(height - 1):
        for c in range(width):
            raw.append((max(matrix[r][c], matrix[r + 1][c]), V_KIND, r, c))
    for r in range(height - 1):
        for c in range(width - 1):
            raw.append(
                (
                    max(
                        matrix[r][c],
                        matrix[r][c + 1],
                        matrix[r + 1][c],
                        matrix[r + 1][c + 1],
                    ),
                    3,
                    r,
                    c,
                )
            )
    raw.sort()

    values: dict[tuple[int, int, int], int] = {}
    orders: dict[tuple[int, int, int], int] = {}
    for order, (value, kind, r, c) in enumerate(raw):
        key = (kind, r, c)
        values[key] = value
        orders[key] = order

    edge_values = {key: value for key, value in values.items() if key[0] in (H_KIND, V_KIND)}

    squares = []
    for r in range(height - 1):
        for c in range(width - 1):
            boundary = {
                (H_KIND, r, c),
                (H_KIND, r + 1, c),
                (V_KIND, r, c),
                (V_KIND, r, c + 1),
            }
            squares.append((orders[(3, r, c)], r, c, boundary))
    squares.sort()
    return orders, edge_values, squares


def edge_endpoint(key: tuple[int, int, int]):
    _, r, c = key
    if key[0] == H_KIND:
        return (r, c), (r, c + 1)
    return (r, c), (r + 1, c)


def independently_check_bar(matrix, body_bar, min_persistence: int) -> None:
    """Re-verify one wire-format bar purely from the raw matrix over GF(2)."""
    orders, edge_values, squares = independent_complex(matrix)

    birth_wire = body_bar["birth_edge"]
    birth_key = (KIND_FROM_WIRE[birth_wire["kind"]], birth_wire["row"], birth_wire["col"])
    death_wire = body_bar["death_square"]
    death_key = (3, death_wire["row"], death_wire["col"])

    birth_order = orders[birth_key]
    death_order = orders[death_key]
    birth_value = edge_values[birth_key]

    # Wire metadata must agree with the independently recomputed order.
    assert birth_wire["value"] == birth_value
    assert birth_wire["order"] == birth_order
    assert death_wire["value"] == max(
        matrix[death_wire["row"]][death_wire["col"]],
        matrix[death_wire["row"]][death_wire["col"] + 1],
        matrix[death_wire["row"] + 1][death_wire["col"]],
        matrix[death_wire["row"] + 1][death_wire["col"] + 1],
    )
    assert death_wire["order"] == death_order
    assert body_bar["birth_value"] == birth_value
    assert body_bar["death_value"] == death_wire["value"]
    assert body_bar["persistence"] == death_wire["value"] - birth_value
    assert death_order > birth_order
    assert death_wire["value"] > birth_value
    assert body_bar["persistence"] >= min_persistence

    cycle_keys = [
        (KIND_FROM_WIRE[e["kind"]], e["row"], e["col"])
        for e in body_bar["birth_cycle"]["edges"]
    ]
    cycle = set(cycle_keys)
    assert body_bar["birth_cycle"]["edge_count"] == len(cycle_keys) == len(cycle)
    assert birth_key in cycle

    # Edges are listed in fixed filtration order, birth edge last.
    cycle_orders = [orders[k] for k in cycle_keys]
    assert cycle_orders == sorted(cycle_orders)
    assert cycle_orders[-1] == birth_order

    # (1) At the birth threshold every vertex has even degree in the chain.
    parity: dict[tuple[int, int], int] = {}
    for key in cycle:
        assert edge_values[key] <= birth_value, "cycle edge enters after birth"
        for vertex in edge_endpoint(key):
            parity[vertex] = parity.get(vertex, 0) ^ 1
    assert not any(parity.values()), "birth cycle is not an even-degree chain"

    # (2) The cycle exists at no earlier threshold: the birth edge is the
    #     unique youngest edge of the chain.
    assert cycle_orders.count(birth_order) == 1
    assert max(cycle_orders) == birth_order

    # (3) Not a boundary below the death square; exactly a boundary once the
    #     death square is added (and the witnessing chain uses that square).
    before = [boundary for order, _, _, boundary in squares if order < death_order]
    assert solve(before, cycle) is None, "cycle already bounds before death square"
    death_boundary = next(boundary for order, _, _, boundary in squares if order == death_order)
    witness = solve(before + [death_boundary], cycle)
    assert witness is not None, "cycle does not bound when the death square enters"
    assert len(before) in witness, "the death square is not in the bounding 2-chain"


def expected_response_bars(matrix, min_persistence: int):
    """Independent GF(2)-rank barcode, filtered and sorted like the service."""
    fil = Filtration(matrix)
    pairs = expected_bar_orders(fil)
    rows = []
    for birth_order, death_order in pairs:
        birth = fil.cells[birth_order]
        death = fil.cells[death_order]
        if death.value > birth.value and death.value - birth.value >= min_persistence:
            rows.append(
                (death.value - birth.value, birth.value, birth_order, death_order)
            )
    rows.sort(key=lambda row: (-row[0], row[1], row[2], row[3]))
    return rows


def assert_response_matches_ground_truth(matrix, body, min_persistence: int) -> None:
    assert body["matrix"] == {"height": len(matrix), "width": len(matrix[0])}
    assert body["min_persistence"] == min_persistence
    assert body["bar_count"] == len(body["bars"])

    expected = expected_response_bars(matrix, min_persistence)
    assert len(body["bars"]) == len(expected)
    for bar, (persistence, birth_value, birth_order, death_order) in zip(body["bars"], expected):
        assert bar["persistence"] == persistence
        assert bar["birth_value"] == birth_value
        assert bar["death_value"] == birth_value + persistence
        assert bar["birth_edge"]["order"] == birth_order
        assert bar["death_square"]["order"] == death_order
        independently_check_bar(matrix, bar, min_persistence)

    # The wire ordering itself must follow the documented rule.
    keys = [
        (
            -bar["persistence"],
            bar["birth_value"],
            bar["birth_edge"]["order"],
            bar["death_square"]["order"],
        )
        for bar in body["bars"]
    ]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Acceptance cases
# ---------------------------------------------------------------------------


def test_health_returns_success():
    http = HttpSession()
    try:
        response = http.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        http.close()


def test_interleaved_holes_matrix_exact_barcode_and_evidence():
    http = HttpSession()
    try:
        response = http.post(
            "/api/v1/barcode",
            {"matrix": TARGET_MATRIX, "min_persistence": 1},
        )
        assert response.status_code == 200
        body = response.json()

        assert body["bar_count"] == 2
        (first, second) = body["bars"]

        assert (first["birth_value"], first["death_value"], first["persistence"]) == (6, 7, 1)
        assert (
            first["birth_edge"]["kind"],
            first["birth_edge"]["endpoints"],
        ) == ("vertical", [[2, 2], [3, 2]])
        assert (first["death_square"]["row"], first["death_square"]["col"]) == (2, 3)

        assert (second["birth_value"], second["death_value"], second["persistence"]) == (7, 8, 1)
        assert (
            second["birth_edge"]["kind"],
            second["birth_edge"]["endpoints"],
        ) == ("vertical", [[2, 0], [3, 0]])
        assert (second["death_square"]["row"], second["death_square"]["col"]) == (2, 1)

        assert_response_matches_ground_truth(TARGET_MATRIX, body, 1)
    finally:
        http.close()


def test_interleaved_holes_both_bars_are_filtered_at_higher_threshold():
    http = HttpSession()
    try:
        response = http.post(
            "/api/v1/barcode",
            {"matrix": TARGET_MATRIX, "min_persistence": 2},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["bar_count"] == 0
        assert body["bars"] == []
    finally:
        http.close()


def test_single_hole_matrix_over_http():
    http = HttpSession()
    try:
        response = http.post(
            "/api/v1/barcode",
            {"matrix": SINGLE_HOLE, "min_persistence": 1},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["bar_count"] == 1
        (bar,) = body["bars"]
        assert (bar["birth_value"], bar["death_value"], bar["persistence"]) == (0, 9, 9)
        assert_response_matches_ground_truth(SINGLE_HOLE, body, 1)
    finally:
        http.close()


def test_two_equal_holes_matrix_with_many_ties():
    http = HttpSession()
    try:
        response = http.post(
            "/api/v1/barcode",
            {"matrix": TWO_EQUAL_HOLES, "min_persistence": 1},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["bar_count"] == 2
        assert [bar["persistence"] for bar in body["bars"]] == [4, 4]
        assert [bar["birth_value"] for bar in body["bars"]] == [1, 1]
        assert_response_matches_ground_truth(TWO_EQUAL_HOLES, body, 1)
    finally:
        http.close()


def test_plateau_ring_matrix_with_large_equal_blocks():
    http = HttpSession()
    try:
        response = http.post(
            "/api/v1/barcode",
            {"matrix": PLATEAU_RING, "min_persistence": 1},
        )
        assert response.status_code == 200
        body = response.json()
        assert_response_matches_ground_truth(PLATEAU_RING, body, 1)
    finally:
        http.close()


def test_constant_matrix_reports_no_bars():
    http = HttpSession()
    try:
        response = http.post(
            "/api/v1/barcode",
            {"matrix": CONSTANT, "min_persistence": 0},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["bar_count"] == 0
        assert body["bars"] == []
        assert_response_matches_ground_truth(CONSTANT, body, 0)
    finally:
        http.close()
