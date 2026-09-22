"""Randomized cross-checks against an independent ground truth.

The barcode produced by the application's GF(2) sparse boundary reduction is
compared, as a multiset of (birth, death) value pairs, against persistent
Betti numbers computed with plain GF(2) rank linear algebra.  Every reported
bar is additionally verified against the three topological guarantees.
"""

import random

from app.filtration import Filtration
from app.persistence import compute_h1_bars
from tests.helpers import check_bar_invariants, expected_bar_orders


def run_crosscheck(matrix):
    fil = Filtration(matrix)
    bars = compute_h1_bars(fil)
    for bar in bars:
        check_bar_invariants(fil, bar)
    # Pair-level comparison: the exact (birth edge, death square) filtration
    # orders must match the persistent-Betti-number multiplicities.
    got_orders = sorted((b.birth_edge.order, b.death_square.order) for b in bars)
    assert got_orders == sorted(expected_bar_orders(fil))
    # Value-level comparison for the bars the API would report.
    got_values = sorted(
        (b.birth_edge.value, b.death_square.value)
        for b in bars
        if b.death_square.value > b.birth_edge.value
    )
    cells = fil.cells
    expected_values = sorted(
        (cells[b].value, cells[d].value)
        for b, d in expected_bar_orders(fil)
        if cells[d].value > cells[b].value
    )
    assert got_values == expected_values


def test_random_small_matrices_with_many_ties():
    rng = random.Random(20260919)
    for _ in range(40):
        height = rng.randint(2, 6)
        width = rng.randint(2, 6)
        vmax = rng.choice([1, 2, 3, 5])
        matrix = [[rng.randint(0, vmax) for _ in range(width)] for _ in range(height)]
        run_crosscheck(matrix)


def test_random_small_matrices_wide_value_range():
    rng = random.Random(777)
    for _ in range(25):
        height = rng.randint(2, 6)
        width = rng.randint(2, 6)
        matrix = [[rng.randint(0, 65535) for _ in range(width)] for _ in range(height)]
        run_crosscheck(matrix)


def test_structured_matrices():
    cases = [
        # single bright peak
        [[0, 0, 0, 0], [0, 9, 9, 0], [0, 9, 9, 0], [0, 0, 0, 0]],
        # two peaks, different heights
        [[0, 0, 0, 0, 0], [0, 9, 0, 4, 0], [0, 0, 0, 0, 0]],
        # ring around a bright core
        [[5, 5, 5, 5, 5], [5, 0, 0, 0, 5], [5, 0, 9, 0, 5], [5, 0, 0, 0, 5], [5, 5, 5, 5, 5]],
        # monotone gradient
        [[r * 10 + c for c in range(5)] for r in range(5)],
        # valley between bright walls
        [[9, 0, 9, 0, 9], [9, 0, 9, 0, 9], [9, 0, 9, 0, 9]],
    ]
    for matrix in cases:
        run_crosscheck(matrix)


def test_medium_random_matrix_smoke():
    rng = random.Random(42)
    matrix = [[rng.randint(0, 1000) for _ in range(24)] for _ in range(24)]
    fil = Filtration(matrix)
    bars = compute_h1_bars(fil)
    for bar in bars:
        check_bar_invariants(fil, bar)
    assert bars  # a noisy 24x24 image certainly has 1-dim classes
