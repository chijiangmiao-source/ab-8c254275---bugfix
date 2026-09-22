"""Shared verification helpers for the test-suite.

Every check here is written against the mathematical contract of the API and
uses only the independent GF(2) helpers from ``tests.gf2`` — never the
application's own reduction internals.
"""

from __future__ import annotations

from app.filtration import H_EDGE, SQUARE, V_EDGE, Filtration
from app.persistence import Bar
from app.service import edge_endpoints
from tests.gf2 import kernel_basis, rank, solve


def check_bar_invariants(filtration: Filtration, bar: Bar) -> None:
    """Assert the three topological guarantees for one reported bar."""
    cycle = bar.cycle_edges

    # (1) At the birth threshold the reported edges form an even-degree
    #     closed chain: every grid vertex is incident to an even number
    #     of cycle edges.
    parity: dict[tuple[int, int], int] = {}
    for edge in cycle:
        for vertex in edge_endpoints(edge):
            parity[vertex] = parity.get(vertex, 0) ^ 1
    assert not any(parity.values()), "birth cycle is not a closed chain"

    # (2) The cycle does not exist at any earlier threshold: the birth edge
    #     is the unique youngest edge of the cycle, so the chain only becomes
    #     available exactly at the birth filtration step.
    orders = [edge.order for edge in cycle]
    assert max(orders) == bar.birth_edge.order
    assert orders.count(bar.birth_edge.order) == 1

    # (3) The class is still alive right before the death square and is
    #     annihilated exactly when the reported square enters: the cycle
    #     bounds no square chain below the death order, but bounds one once
    #     the death square is included.
    target = {edge.order for edge in cycle}
    boundaries_before = [
        set(filtration.boundary(cell))
        for cell in filtration.cells
        if cell.kind == SQUARE and cell.order < bar.death_square.order
    ]
    assert solve(boundaries_before, target) is None, (
        "cycle already null-homologous before the reported death square"
    )
    boundaries_at = boundaries_before + [set(filtration.boundary(bar.death_square))]
    assert solve(boundaries_at, target) is not None, (
        "cycle not null-homologous at the reported death square"
    )


def expected_bar_orders(filtration: Filtration) -> list[tuple[int, int]]:
    """Ground-truth barcode as (birth order, death order) pairs.

    For filtration indices ``i <= j`` let beta(i, j) be the rank of the map
    H1(K_i) -> H1(K_j).  The multiplicity of the pair (b, d) is

        mu(b, d) = beta(b, d-1) - beta(b, d) - beta(b-1, d-1) + beta(b-1, d).

    Computed with plain GF(2) ranks; independent of the app's reduction.
    """
    cells = filtration.cells
    edges = [c for c in cells if c.kind in (H_EDGE, V_EDGE)]
    squares = [c for c in cells if c.kind == SQUARE]
    d1 = {e.order: set(filtration.boundary(e)) for e in edges}
    d2 = {s.order: set(filtration.boundary(s)) for s in squares}

    def beta(i: int, j: int) -> int:
        if i < 0 or j < i:
            return 0
        edge_list = [e for e in edges if e.order <= i]
        edge_cols = [d1[e.order] for e in edge_list]
        square_cols = [d2[s.order] for s in squares if s.order <= j]
        kernel = kernel_basis(edge_cols)
        kernel_vecs = [{edge_list[t].order for t in combo} for combo in kernel]
        # dim Z1 - dim(Z1 ∩ B1) = dim(Z1 + B1) - dim B1
        return rank(kernel_vecs + square_cols) - rank(square_cols)

    expected: list[tuple[int, int]] = []
    for edge in edges:
        for square in squares:
            if square.order <= edge.order:
                continue
            b, d = edge.order, square.order
            mu = beta(b, d - 1) - beta(b, d) - beta(b - 1, d - 1) + beta(b - 1, d)
            assert mu >= 0
            expected.extend([(b, d)] * mu)
    return expected
