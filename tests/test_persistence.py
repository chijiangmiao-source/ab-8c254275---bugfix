"""Hand-checkable persistence scenarios and per-bar topological invariants."""

from app.filtration import Filtration
from app.persistence import compute_h1_bars
from tests.helpers import check_bar_invariants


def real_bars(matrix):
    """All bars with death > birth; invariants checked on every raw bar."""
    fil = Filtration(matrix)
    raw = compute_h1_bars(fil)
    for bar in raw:
        check_bar_invariants(fil, bar)
    return fil, [b for b in raw if b.death_square.value > b.birth_edge.value]


def test_bright_center_hole():
    # Dark ring (0) closes at threshold 0; the bright center (9) fills the
    # hole at threshold 9 -> one bar of persistence 9.
    _, bars = real_bars([[0, 0, 0], [0, 9, 0], [0, 0, 0]])
    assert len(bars) == 1
    bar = bars[0]
    assert bar.birth_edge.value == 0
    assert bar.death_square.value == 9
    assert bar.persistence == 9
    assert len(bar.cycle_edges) == 8  # the outer ring of edges


def test_two_holes():
    _, bars = real_bars(
        [
            [0, 0, 0, 0, 0],
            [0, 9, 0, 4, 0],
            [0, 0, 0, 0, 0],
        ]
    )
    assert sorted((b.persistence for b in bars), reverse=True) == [9, 4]


def test_constant_image_has_no_positive_persistence_bars():
    fil = Filtration([[7, 7, 7], [7, 7, 7], [7, 7, 7]])
    bars = compute_h1_bars(fil)
    assert all(b.death_square.value == b.birth_edge.value for b in bars)


def test_two_by_two_has_no_real_bar():
    _, bars = real_bars([[0, 1], [2, 3]])
    assert bars == []


def test_checkerboard_has_no_real_bar():
    matrix = [[(r + c) % 2 for c in range(6)] for r in range(6)]
    _, bars = real_bars(matrix)
    assert bars == []


def test_every_raw_bar_satisfies_invariants():
    # real_bars() runs check_bar_invariants on every computed bar, including
    # the zero-persistence ones that the API later filters out.
    matrix = [
        [3, 1, 4, 1],
        [5, 9, 2, 6],
        [5, 3, 5, 8],
        [9, 7, 9, 3],
    ]
    fil = Filtration(matrix)
    raw = compute_h1_bars(fil)
    assert raw  # sanity: this matrix does produce pairs
    for bar in raw:
        check_bar_invariants(fil, bar)
