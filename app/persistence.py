"""1-dimensional persistence via GF(2) sparse boundary reduction.

The boundary matrix of the cubical complex is reduced column by column in
filtration order over GF(2) — the classic left-to-right reduction, implemented
here from scratch on sparse sets (no external persistent-homology library):

* a column that reduces to zero is *positive*: it creates a homology class;
* a column whose reduced form is non-empty is *negative*: it kills the class
  created by the row index of its lowest entry (``low``).

A 1-dimensional bar is a pair (edge ``e``, square ``s``) where the reduced
boundary of square ``s`` has ``low = e``.  The reduced boundary itself is
reported as the bar's birth cycle: it is a closed even-degree edge chain whose
youngest edge is exactly ``e`` (so the chain exists from the birth threshold
on and no earlier), and it is annihilated precisely when square ``s`` enters —
it is the boundary of the 2-chain accumulated while reducing column ``s``,
and it bounds no 2-chain below ``s``.

The full grid complex is a solid rectangle, hence contractible, so every
1-class that is born also dies: the barcode is finite and every reported bar
has a concrete birth edge and death square.
"""

from __future__ import annotations

from dataclasses import dataclass

from .filtration import SQUARE, VERTEX, Cell, Filtration


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

    low_to_col: dict[int, int] = {}     # lowest row of a reduced column -> that column
    reduced_cols: dict[int, set[int]] = {}  # negative columns: reduced boundary
    parent = list(range(len(cells)))
    rank = [0] * len(cells)
    forest: list[list[tuple[int, int]]] = [[] for _ in cells]

    bars: list[Bar] = []

    def find(vertex: int) -> int:
        root = vertex
        while parent[root] != root:
            root = parent[root]
        while parent[vertex] != vertex:
            next_vertex = parent[vertex]
            parent[vertex] = root
            vertex = next_vertex
        return root

    def cycle_edges(start: int, end: int, closing_edge: int) -> set[int]:
        previous: dict[int, tuple[int, int] | None] = {start: None}
        pending = [start]
        while pending:
            vertex = pending.pop()
            if vertex == end:
                break
            for neighbor, edge_order in forest[vertex]:
                if neighbor not in previous:
                    previous[neighbor] = (vertex, edge_order)
                    pending.append(neighbor)

        cycle = {closing_edge}
        vertex = end
        while vertex != start:
            predecessor = previous[vertex]
            if predecessor is None:
                break
            vertex, edge_order = predecessor
            cycle.add(edge_order)
        return cycle

    for j, cell in enumerate(cells):
        if cell.kind == VERTEX:
            # Empty boundary: positive, creates an H0 class; irrelevant for H1.
            continue

        if cell.kind != SQUARE:
            start, end = boundaries[j]
            start_root = find(start)
            end_root = find(end)
            if start_root != end_root:
                if rank[start_root] < rank[end_root]:
                    start_root, end_root = end_root, start_root
                parent[end_root] = start_root
                if rank[start_root] == rank[end_root]:
                    rank[start_root] += 1
                forest[start].append((end, j))
                forest[end].append((start, j))
                continue
            # Positive cell: a class is born.  For an edge this is an H1
            # birth; nothing needs to be stored — the bar is reported when
            # the killing square is reduced.
            low_to_col[j] = j
            reduced_cols[j] = cycle_edges(start, end, j)
            continue

        low, _ = low_to_col.popitem()
        col = reduced_cols.pop(low)
        if cell.kind == SQUARE:
            # `low` is a positive edge (standard invariant of the reduction);
            # pair it with this square.  The reduced boundary `col` is the
            # birth cycle: a closed edge chain, youngest edge == low, killed
            # exactly by this square.
            bars.append(
                Bar(
                    birth_edge=cells[low],
                    death_square=cell,
                    cycle_edges=tuple(cells[i] for i in sorted(col)),
                )
            )

    return bars
