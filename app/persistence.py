"""1-dimensional persistence via GF(2) sparse boundary reduction.

The full boundary matrix of the cubical complex is reduced column by column
in filtration order over GF(2) — the classic left-to-right reduction,
implemented from scratch on sparse sets (no external persistent-homology
library):

* a column that reduces to zero is *positive*: it creates a homology class;
* a column whose reduced form is non-empty is *negative*: it kills the class
  created by the row index of its lowest (highest-order) entry ``low``.

Every column is reduced against previously reduced pivot columns only, always
chasing the lowest (maximum-order) row.  This strict pivot rule is what makes
the pairing canonical: with several holes born and dying at interleaved
thresholds, a square may first cancel the youngest edge of another class's
reduced boundary before its own pivot surfaces — skipping those additions
(or pairing the square with an arbitrary unpaired positive edge) merges
distinct classes into a bogus long-lived bar.

A 1-dimensional bar is a pair (edge ``e``, square ``s``) where the reduced
boundary of square ``s`` has ``low = e``.  The reduced boundary itself is
reported as the bar's birth cycle: it is a sum of original square boundaries,
hence a closed even-degree edge chain whose youngest edge is exactly ``e``
(so the chain exists from the birth threshold on and no earlier), and it is
annihilated precisely when square ``s`` enters — below ``s`` it bounds no
2-chain, and adding the boundary of ``s`` makes it one.

The full grid complex is a solid rectangle, hence contractible, so every
1-class that is born also dies: the barcode is finite and every reported bar
has a concrete birth edge and death square.
"""

from __future__ import annotations

from dataclasses import dataclass

from .filtration import H_EDGE, SQUARE, V_EDGE, Cell, Filtration

_EDGE_KINDS = (H_EDGE, V_EDGE)


@dataclass(frozen=True)
class Bar:
    """One 1-dimensional persistence bar.

    ``cycle_edges`` are the edges of the reported birth cycle (the reduced
    boundary of the death square), sorted by filtration order — the fixed
    order in which the reduction consumed them.  The last edge is always the
    birth edge itself.
    """

    birth_edge: Cell
    death_square: Cell
    cycle_edges: tuple[Cell, ...]

    @property
    def persistence(self) -> int:
        return self.death_square.value - self.birth_edge.value


def compute_h1_bars(filtration: Filtration) -> list[Bar]:
    """Reduce the boundary matrix and return every 1-dimensional bar.

    Bars with ``death_value == birth_value`` (zero persistence) are included
    here; the service layer applies the persistence filters.
    """
    cells = filtration.cells
    boundaries = filtration.boundaries
    n = len(cells)

    # Reduced pivot columns, kept by column index for columns that reduced
    # to a non-zero form; None for positive (zero) columns.  Each entry is a
    # sparse set of row indices (cell filtration orders).
    reduced: list[set[int] | None] = [None] * n
    # Pivot row -> column owning a reduced column with that lowest entry.
    pivot_column: dict[int, int] = {}

    for j in range(n):
        col = set(boundaries[j])
        while col:
            low = max(col)
            owner = pivot_column.get(low)
            if owner is None:
                break
            # Left-add the pivot column: cancel the shared lowest entry and
            # any other common rows over GF(2).
            col ^= reduced[owner]  # type: ignore[operator]
        if col:
            # Negative column: its lowest row pairs it with that positive cell.
            pivot_column[max(col)] = j
            reduced[j] = col

    bars: list[Bar] = []
    for j, col in enumerate(reduced):
        if not col:
            continue
        death_cell = cells[j]
        if death_cell.kind != SQUARE:
            continue  # (vertex, edge) pairs are 0-dimensional bars
        birth_index = max(col)
        birth_cell = cells[birth_index]
        if birth_cell.kind not in _EDGE_KINDS:
            # Cannot happen for a valid cubical filtration, but keep the
            # pairing honest rather than emitting a malformed bar.
            continue
        # A reduced square column is a boundary of a 2-chain, hence a closed
        # edge chain: every surviving row indexes an edge (vertex terms cancel
        # in pairs while reducing against the edge columns).
        cycle = tuple(cells[i] for i in sorted(col))
        bars.append(
            Bar(
                birth_edge=birth_cell,
                death_square=death_cell,
                cycle_edges=cycle,
            )
        )

    return bars
