"""Lower-star cubical filtration of a 2-D grayscale image.

For an ``H x W`` gray matrix the cubical complex contains

* ``H * W``         vertices          ``(r, c)``     value ``g[r][c]``
* ``H * (W - 1)``   horizontal edges  ``(r, c)``     value ``max(g[r][c], g[r][c+1])``
* ``(H - 1) * W``   vertical edges    ``(r, c)``     value ``max(g[r][c], g[r+1][c])``
* ``(H-1) * (W-1)`` squares           ``(r, c)``     value ``max`` of the 4 corners

Cells enter the filtration in ascending value; ties are broken by cell kind
(vertex < horizontal edge < vertical edge < square) and then by row and
column.  Because every face of a cell has value <= the cell's value and a
strictly smaller kind on ties, this total order is a valid filtration: faces
always precede their cofaces.  The position of a cell in this order is its
``order`` (0-based); it is the single deterministic sequence in which the
GF(2) boundary reduction consumes the cells.
"""

from __future__ import annotations

from dataclasses import dataclass

VERTEX = 0
H_EDGE = 1
V_EDGE = 2
SQUARE = 3

KIND_NAMES = {
    VERTEX: "vertex",
    H_EDGE: "horizontal_edge",
    V_EDGE: "vertical_edge",
    SQUARE: "square",
}


@dataclass(frozen=True)
class Cell:
    """A cell of the cubical complex, placed at ``order`` in the filtration."""

    value: int
    kind: int
    row: int
    col: int
    order: int


class Filtration:
    """The sorted cells of the complex plus face lookups by filtration order."""

    def __init__(self, matrix: list[list[int]]) -> None:
        self.height = height = len(matrix)
        self.width = width = len(matrix[0])

        raw: list[tuple[int, int, int, int]] = []
        for r in range(height):
            for c in range(width):
                raw.append((matrix[r][c], VERTEX, r, c))
        for r in range(height):
            for c in range(width - 1):
                raw.append((max(matrix[r][c], matrix[r][c + 1]), H_EDGE, r, c))
        for r in range(height - 1):
            for c in range(width):
                raw.append((max(matrix[r][c], matrix[r + 1][c]), V_EDGE, r, c))
        for r in range(height - 1):
            for c in range(width - 1):
                value = max(
                    matrix[r][c],
                    matrix[r][c + 1],
                    matrix[r + 1][c],
                    matrix[r + 1][c + 1],
                )
                raw.append((value, SQUARE, r, c))

        # Tuple order is exactly (value, kind, row, col): the documented
        # filtration order with its tie-breaking rules.
        raw.sort()

        self.cells: list[Cell] = [
            Cell(value=value, kind=kind, row=r, col=c, order=order)
            for order, (value, kind, r, c) in enumerate(raw)
        ]

        # position -> filtration order, per kind
        self.vertex_order = [[0] * width for _ in range(height)]
        self.h_edge_order = [[0] * (width - 1) for _ in range(height)]
        self.v_edge_order = [[0] * width for _ in range(height - 1)]
        self.square_order = [[0] * (width - 1) for _ in range(height - 1)]
        for cell in self.cells:
            if cell.kind == VERTEX:
                self.vertex_order[cell.row][cell.col] = cell.order
            elif cell.kind == H_EDGE:
                self.h_edge_order[cell.row][cell.col] = cell.order
            elif cell.kind == V_EDGE:
                self.v_edge_order[cell.row][cell.col] = cell.order
            else:
                self.square_order[cell.row][cell.col] = cell.order

        # Boundary of every cell, expressed in filtration orders.  Vertices
        # have an empty boundary; every face precedes its coface, so each
        # boundary only contains smaller orders.
        self.boundaries: list[tuple[int, ...]] = [
            self._boundary(cell) for cell in self.cells
        ]

    def boundary(self, cell: Cell) -> tuple[int, ...]:
        """Filtration orders of the cell's boundary faces."""
        return self.boundaries[cell.order]

    def _boundary(self, cell: Cell) -> tuple[int, ...]:
        r, c = cell.row, cell.col
        if cell.kind == VERTEX:
            return ()
        if cell.kind == H_EDGE:
            return (self.vertex_order[r][c], self.vertex_order[r][c + 1])
        if cell.kind == V_EDGE:
            return (self.vertex_order[r][c], self.vertex_order[r + 1][c])
        return (
            self.h_edge_order[r][c],
            self.h_edge_order[r + 1][c],
            self.v_edge_order[r][c],
            self.v_edge_order[r][c + 1],
        )
