"""Small, obviously-correct GF(2) linear algebra helpers (test-suite only).

These routines are deliberately naive and independent from the application's
reduction code, so the cross-checks actually mean something.
"""

from __future__ import annotations


def reduce_basis(vectors: list[set[int]]) -> dict[int, set[int]]:
    """Echelon basis of the span of ``vectors``; maps pivot -> basis vector."""
    basis: dict[int, set[int]] = {}
    for vector in vectors:
        v = set(vector)
        while v:
            pivot = max(v)
            other = basis.get(pivot)
            if other is None:
                basis[pivot] = v
                break
            v ^= other
    return basis


def rank(vectors: list[set[int]]) -> int:
    return len(reduce_basis(vectors))


def kernel_basis(columns: list[set[int]]) -> list[set[int]]:
    """Basis of the kernel of the map whose columns are given.

    Returns a list of kernel vectors, each a set of column indices.
    """
    basis: dict[int, tuple[set[int], set[int]]] = {}
    kernel: list[set[int]] = []
    for i, column in enumerate(columns):
        v = set(column)
        combo = {i}
        while v:
            pivot = max(v)
            other = basis.get(pivot)
            if other is None:
                basis[pivot] = (v, combo)
                break
            v ^= other[0]
            combo ^= other[1]
        else:
            kernel.append(combo)
    return kernel


def solve(columns: list[set[int]], target: set[int]) -> set[int] | None:
    """Find column indices summing to ``target`` over GF(2), or ``None``."""
    basis: dict[int, tuple[set[int], set[int]]] = {}
    for i, column in enumerate(columns):
        v = set(column)
        combo = {i}
        while v:
            pivot = max(v)
            other = basis.get(pivot)
            if other is None:
                basis[pivot] = (v, combo)
                break
            v ^= other[0]
            combo ^= other[1]
    v = set(target)
    combo: set[int] = set()
    while v:
        pivot = max(v)
        other = basis.get(pivot)
        if other is None:
            return None
        v ^= other[0]
        combo ^= other[1]
    return combo
