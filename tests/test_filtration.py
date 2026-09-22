"""Filtration construction: values, tie-breaking, and face-before-coface."""

from app.filtration import H_EDGE, SQUARE, V_EDGE, VERTEX, Filtration


def test_cell_counts():
    fil = Filtration([[1, 2, 3], [4, 5, 6]])
    kinds = [c.kind for c in fil.cells]
    assert kinds.count(VERTEX) == 6
    assert kinds.count(H_EDGE) == 4
    assert kinds.count(V_EDGE) == 3
    assert kinds.count(SQUARE) == 2
    assert len(fil.cells) == 15


def test_filtration_values():
    matrix = [[10, 20], [30, 40]]
    fil = Filtration(matrix)
    by_kind = {}
    for cell in fil.cells:
        by_kind.setdefault(cell.kind, []).append(cell.value)
    assert sorted(by_kind[VERTEX]) == [10, 20, 30, 40]
    assert by_kind[H_EDGE] == [20, 40]          # max of horizontal neighbors
    assert by_kind[V_EDGE] == [30, 40]          # max of vertical neighbors
    assert by_kind[SQUARE] == [40]              # max of the four corners


def test_tie_break_order_vertex_then_hedge_then_vedge_then_square():
    # Constant image: every cell has value 5, so the order is purely the
    # documented tie-break: kind, then row, then column.
    fil = Filtration([[5, 5], [5, 5]])
    keys = [(c.kind, c.row, c.col) for c in fil.cells]
    assert keys == [
        (VERTEX, 0, 0),
        (VERTEX, 0, 1),
        (VERTEX, 1, 0),
        (VERTEX, 1, 1),
        (H_EDGE, 0, 0),
        (H_EDGE, 1, 0),
        (V_EDGE, 0, 0),
        (V_EDGE, 0, 1),
        (SQUARE, 0, 0),
    ]


def test_faces_precede_cofaces():
    # For every cell, every face must appear strictly earlier in the order.
    fil = Filtration([[3, 1, 4], [1, 5, 9], [2, 6, 5]])
    for cell in fil.cells:
        for face in fil.boundary(cell):
            assert face < cell.order


def test_boundary_contents():
    fil = Filtration([[1, 2], [3, 4]])
    square = next(c for c in fil.cells if c.kind == SQUARE)
    boundary = set(fil.boundary(square))
    assert boundary == {
        fil.h_edge_order[0][0],
        fil.h_edge_order[1][0],
        fil.v_edge_order[0][0],
        fil.v_edge_order[0][1],
    }
