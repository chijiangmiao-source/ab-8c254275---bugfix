"""1-dimensional persistence via GF(2) sparse boundary reduction.

The boundary matrix of the cubical complex is reduced column by column in
filtration order over GF(2) — the classic left-to-right reduction, implemented
here from scratch on sparse sets (no external persistent-homology library):

* maintain, for every pivot row ``low``, the previously reduced column whose
  youngest (highest-indexed) entry is ``low``;
* to reduce column ``j``, repeatedly XOR the pivot column registered at its
  current lowest entry until the column is either empty (a *negative* column)
  or its lowest entry is free (a *positive* column, which registers a new
  pivot ``low -> j``);
* a pivot pair ``(low, j)`` pairs a birth cell (the row cell ``low``) with a
  death cell (column ``j``).

A 1-dimensional bar is a pair (edge ``e``, square ``s``) where the reduced
boundary of square ``s`` has its pivot on edge ``e``.  The reduced boundary
itself is reported as the bar's birth cycle:

* every square column starts as an edge-only chain and is only ever XORed with
  other square columns, so its reduced form is an edge chain; the pivot edge
  is its unique youngest edge;
* it is a cycle (zero 1-boundary): reduction against the *unreduced* boundary
  of ``s`` gives zero, hence it is the boundary of the 2-chain accumulated
  while reducing column ``s``;
* that 2-chain contains no square at or above ``s`` in a way the squares below
  ``s`` could reproduce, so the chain bounds no 2-chain before ``s`` enters and
  is annihilated precisely when square ``s`` enters — this is the standard
  persistence-pairing guarantee of the left-to-right reduction.

The full grid complex is a solid rectangle, hence contractible, so every
1-class that is born also dies: the barcode is finite and every reported bar
has a concrete birth edge and death square.
"""

from __future__ import annotations

from dataclasses import dataclass

from .filtration import H_EDGE, SQUARE, V_EDGE, Cell, Filtration


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

    # pivot row index -> index of the reduced column owning that pivot
    pivot_column: dict[int, int] = {}
    # reduced column index -> its reduced sparse boundary (a set of row indices)
    reduced_columns: dict[int, set[int]] = {}

    bars: list[Bar] = []

    for j, cell in enumerate(cells):
        # A fresh working copy: the stored reduced columns must stay frozen
        # once their pivot is registered.
        column = set(boundaries[j])
        while column:
            low = max(column)
            owner = pivot_column.get(low)
            if owner is not None:
                # Left-addition over GF(2) kills the current lowest entry.
                column ^= reduced_columns[owner]
                continue
            # `low` is a free pivot: column j is positive and pairs the row
            # cell `low` with this column's cell.
            pivot_column[low] = j
            reduced_columns[j] = column
            birth_cell = cells[low]
            if cell.kind == SQUARE and birth_cell.kind in (H_EDGE, V_EDGE):
                # Square column pivoting on an edge: the edge creates an H1
                # class exactly when it enters, and this square kills it.
                # `column` is the reduced boundary: an even-degree edge chain
                # whose unique youngest edge is the birth edge.
                bars.append(
                    Bar(
                        birth_edge=birth_cell,
                        death_square=cell,
                        cycle_edges=tuple(cells[i] for i in sorted(column)),
                    )
                )
            break
        # An exhausted (empty) column is negative and creates no pair here;
        # its pairing was already recorded when its pivot column was reduced.

    return bars
