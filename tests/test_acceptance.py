"""End-to-end acceptance tests for the barcode pairing/evidence consistency fix.

These tests go through the public HTTP interface (``POST /api/v1/barcode`` and
``GET /health``) and never touch the application's reduction internals.  Every
reported bar is re-derived from the raw matrix and re-checked independently with
the naive GF(2) helpers in ``tests.gf2``:

1. at the birth threshold every vertex of the reported cycle has even degree;
2. the cycle exists at no earlier threshold — its birth edge is the unique
   youngest edge of the chain;
3. the cycle is not the boundary of any square combination below the reported
   death square, and becomes a boundary exactly when that square is added (the
   annihilating 2-chain contains the death square itself).

The headline case is a 4x5 matrix whose two holes have interleaved lifetimes
(birth 6 / death 7 and birth 7 / death 8): a naive reducer merges them into a
single bogus persistence-2 bar, while the correct verdict is two bars.
"""

from __future__ import annotations

import random

from fastapi.testclient import TestClient

from app.filtration import H_EDGE, SQUARE, V_EDGE, Filtration
from app.main import app
from tests.gf2 import solve

client = TestClient(app)


INTERLEAVED_HOLES = [
    [7, 7, 2, 9, 5],
    [5, 5, 6, 3, 5],
    [7, 8, 6, 7, 4],
    [1, 1, 3, 4, 3],
]
SINGLE_HOLE = [[0, 0, 0], [0, 9, 0], [0, 0, 0]]
# A mostly-flat slab (many equal 0 cells) with two bright inclusions, plus a
# third inclusion in the lower half: heavy ties and several interleaved bars.
FLAT_WITH_HOLES = [
    [0, 0, 0, 0, 0, 0],
    [0, 9, 0, 0, 4, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 9, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
]


def post_barcode(matrix, min_persistence=1):
    return client.post(
        "/api/v1/barcode",
        json={"matrix": matrix, "min_persistence": min_persistence},
    )


def assert_bar_evidenced_consistently(matrix, bar) -> None:
    """Independently re-verify one HTTP-reported bar against the raw matrix."""
    fil = Filtration(matrix)
    square_boundary = {
        cell.order: set(fil.boundary(cell))
        for cell in fil.cells
        if cell.kind == SQUARE
    }

    cycle_edges = bar["birth_cycle"]["edges"]
    edge_orders = [edge["order"] for edge in cycle_edges]
    edge_order_set = set(edge_orders)

    # The payload lists the cycle in fixed filtration order, ending with the
    # birth edge.
    assert edge_orders == sorted(edge_orders)
    assert edge_orders[-1] == bar["birth_edge"]["order"]
    assert bar["birth_cycle"]["edge_count"] == len(cycle_edges)

    # (1) Even-degree closed chain at the birth threshold.
    parity: dict[tuple[int, int], int] = {}
    for edge in cycle_edges:
        assert edge["value"] <= bar["birth_value"]
        for endpoint in edge["endpoints"]:
            key = tuple(endpoint)
            parity[key] = parity.get(key, 0) ^ 1
    assert not any(parity.values()), "vertex of the birth cycle has odd degree"

    # (2) The cycle exists at no earlier threshold: the birth edge is its
    #     unique youngest edge.
    birth_order = bar["birth_edge"]["order"]
    assert max(edge_orders) == birth_order
    assert edge_orders.count(birth_order) == 1

    # (3) Alive just before the death square, dead exactly when it enters.
    death_order = bar["death_square"]["order"]
    assert death_order > birth_order
    boundaries_before = [
        square_boundary[order]
        for order in square_boundary
        if order < death_order
    ]
    assert solve(boundaries_before, edge_order_set) is None, (
        "birth cycle is already a boundary before the reported death square"
    )
    boundaries_at = boundaries_before + [square_boundary[death_order]]
    filling = solve(boundaries_at, edge_order_set)
    assert filling is not None, (
        "birth cycle is not annihilated by the reported death square"
    )
    # The annihilating 2-chain must use the reported death square: otherwise
    # the cycle would already have been a boundary before it entered.
    assert len(boundaries_at) - 1 in filling


def assert_response_well_formed(matrix, body) -> None:
    height, width = len(matrix), len(matrix[0])
    assert body["matrix"] == {"height": height, "width": width}
    assert body["bar_count"] == len(body["bars"])
    for bar in body["bars"]:
        assert bar["persistence"] == bar["death_value"] - bar["birth_value"]
        assert bar["persistence"] >= 1
        assert_bar_evidenced_consistently(matrix, bar)
    # Reported ranking: persistence descending, then birth value, then the
    # documented filtration order of the birth edge and death square.
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


def test_health_is_successful():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_interleaved_holes_are_two_separate_bars():
    response = post_barcode(INTERLEAVED_HOLES, min_persistence=1)
    assert response.status_code == 200
    body = response.json()

    assert body["bar_count"] == 2
    first, second = body["bars"]

    # Adjudication order: equal persistence 1, smaller birth value first.
    assert (first["birth_value"], first["death_value"]) == (6, 7)
    assert (second["birth_value"], second["death_value"]) == (7, 8)
    assert first["persistence"] == second["persistence"] == 1

    # First bar: vertical birth edge (2,2)-(3,2), death square at (2,3).
    assert first["birth_edge"]["kind"] == "vertical"
    assert first["birth_edge"]["endpoints"] == [[2, 2], [3, 2]]
    assert (first["death_square"]["row"], first["death_square"]["col"]) == (2, 3)

    # Second bar: vertical birth edge (2,0)-(3,0), death square at (2,1).
    assert second["birth_edge"]["kind"] == "vertical"
    assert second["birth_edge"]["endpoints"] == [[2, 0], [3, 0]]
    assert (second["death_square"]["row"], second["death_square"]["col"]) == (2, 1)

    assert_response_well_formed(INTERLEAVED_HOLES, body)

    # The two fixed reduced birth cycles must be distinct chains, not one
    # long-lived merged record.
    def edge_set(bar):
        return {
            (tuple(edge["endpoints"][0]), tuple(edge["endpoints"][1]))
            for edge in bar["birth_cycle"]["edges"]
        }

    assert edge_set(first) != edge_set(second)


def test_interleaved_holes_respect_persistence_threshold():
    # Nothing changes about filtering: both bars have persistence exactly 1.
    body = post_barcode(INTERLEAVED_HOLES, min_persistence=1).json()
    assert body["bar_count"] == 2
    body = post_barcode(INTERLEAVED_HOLES, min_persistence=2).json()
    assert body["bar_count"] == 0


def test_single_hole_matrix():
    response = post_barcode(SINGLE_HOLE, min_persistence=1)
    assert response.status_code == 200
    body = response.json()

    assert body["bar_count"] == 1
    (bar,) = body["bars"]
    assert (bar["birth_value"], bar["death_value"], bar["persistence"]) == (0, 9, 9)
    assert (bar["death_square"]["row"], bar["death_square"]["col"]) == (1, 1)
    assert bar["birth_cycle"]["edge_count"] == 8  # the outer ring of edges

    assert_response_well_formed(SINGLE_HOLE, body)


def test_flat_matrix_with_many_equal_cells():
    response = post_barcode(FLAT_WITH_HOLES, min_persistence=1)
    assert response.status_code == 200
    body = response.json()

    # Two 0->9 inclusions and one 0->4 inclusion, all born over the same flat
    # sea of equal-valued cells.
    assert body["bar_count"] == 3
    assert [(b["birth_value"], b["death_value"]) for b in body["bars"]] == [
        (0, 9),
        (0, 9),
        (0, 4),
    ]
    assert_response_well_formed(FLAT_WITH_HOLES, body)


def test_fully_constant_matrix_reports_no_bars():
    matrix = [[7] * 5 for _ in range(4)]
    response = post_barcode(matrix, min_persistence=1)
    assert response.status_code == 200
    body = response.json()
    assert body["bar_count"] == 0
    assert body["bars"] == []

    # Even with the threshold lowered to zero, same-valued birth/death pairs
    # remain filtered out.
    body = post_barcode(matrix, min_persistence=0).json()
    assert body["bar_count"] == 0


def test_large_two_value_matrix_with_massive_ties():
    rng = random.Random(20260922)
    matrix = [[rng.randint(0, 1) for _ in range(16)] for _ in range(12)]
    response = post_barcode(matrix, min_persistence=1)
    assert response.status_code == 200
    body = response.json()
    # Every surviving bar spans the only possible gap 0 -> 1; check counts,
    # ordering, and independently re-verify every fixed reduced birth cycle.
    for bar in body["bars"]:
        assert (bar["birth_value"], bar["death_value"]) == (0, 1)
    assert_response_well_formed(matrix, body)


def test_edge_payload_references_real_filtration_cells():
    # Every order reported over the wire must identify the same cell when the
    # filtration is rebuilt independently from the raw matrix.
    body = post_barcode(INTERLEAVED_HOLES).json()
    fil = Filtration(INTERLEAVED_HOLES)
    by_order = {cell.order: cell for cell in fil.cells}
    for bar in body["bars"]:
        for edge in bar["birth_cycle"]["edges"] + [bar["birth_edge"]]:
            cell = by_order[edge["order"]]
            assert cell.kind in (H_EDGE, V_EDGE)
            assert cell.value == edge["value"]
            assert (cell.row, cell.col) == (edge["row"], edge["col"])
        square = by_order[bar["death_square"]["order"]]
        assert square.kind == SQUARE
        assert square.value == bar["death_value"]
        assert (square.row, square.col) == (
            bar["death_square"]["row"],
            bar["death_square"]["col"],
        )
