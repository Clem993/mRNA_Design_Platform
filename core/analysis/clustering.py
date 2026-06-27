"""
Sequence clustering and tree building for worklist exploration.

Provides a lightweight, dependency-light pipeline (numpy only) analogous to an
immune-repertoire clustering view:

  1. ``kmer_distance_matrix`` — k-mer cosine distance between sequences.
  2. ``upgma`` — average-linkage hierarchical clustering → a SciPy-style
     ``linkage`` array plus a leaf ordering for plotting a dendrogram.
  3. ``flat_clusters`` — cut the tree at a distance threshold into flat clusters.

Everything works on raw nucleotide strings; no alignment required.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


def kmer_counts(seq: str, k: int = 4) -> Counter:
    """Count k-mers in a sequence (DNA alphabet, U→T)."""
    s = (seq or "").upper().replace("U", "T")
    if len(s) < k:
        return Counter()
    return Counter(s[i:i + k] for i in range(len(s) - k + 1))


def _cosine_distance(a: Counter, b: Counter) -> float:
    """1 - cosine similarity between two k-mer count vectors."""
    if not a or not b:
        return 1.0
    # dot product over shared keys
    shared = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in shared)
    na = np.sqrt(sum(v * v for v in a.values()))
    nb = np.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 1.0
    cos = dot / (na * nb)
    return float(max(0.0, 1.0 - cos))


def kmer_distance_matrix(sequences: List[str], k: int = 4) -> np.ndarray:
    """Symmetric pairwise k-mer cosine distance matrix (n×n)."""
    vecs = [kmer_counts(s, k) for s in sequences]
    n = len(vecs)
    d = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            dist = _cosine_distance(vecs[i], vecs[j])
            d[i, j] = d[j, i] = dist
    return d


def upgma(dist: np.ndarray) -> Tuple[np.ndarray, List[int]]:
    """
    Average-linkage (UPGMA) hierarchical clustering.

    Parameters
    ----------
    dist : np.ndarray
        Square symmetric distance matrix (n×n).

    Returns
    -------
    linkage : np.ndarray
        SciPy-style (n-1)×4 array: each row [id_a, id_b, height, size].
        Leaf ids are 0..n-1; internal nodes get ids n, n+1, …
    leaf_order : list[int]
        Left-to-right leaf ordering for plotting a non-crossing dendrogram.
    """
    n = dist.shape[0]
    if n < 2:
        return np.empty((0, 4)), list(range(n))

    # active clusters: id -> (members, size). distances kept in a dict.
    sizes: Dict[int, int] = {i: 1 for i in range(n)}
    members: Dict[int, List[int]] = {i: [i] for i in range(n)}
    active = list(range(n))
    D: Dict[Tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            D[(i, j)] = dist[i, j]

    def key(a: int, b: int) -> Tuple[int, int]:
        return (a, b) if a < b else (b, a)

    linkage = []
    next_id = n
    while len(active) > 1:
        # find closest pair
        best = None
        best_pair = None
        for ai in range(len(active)):
            for bi in range(ai + 1, len(active)):
                a, b = active[ai], active[bi]
                dval = D[key(a, b)]
                if best is None or dval < best:
                    best = dval
                    best_pair = (a, b)
        a, b = best_pair
        new = next_id
        next_id += 1
        sa, sb = sizes[a], sizes[b]
        members[new] = members[a] + members[b]
        sizes[new] = sa + sb
        linkage.append([float(a), float(b), float(best), float(sizes[new])])

        # update distances (average linkage weighted by size)
        for c in active:
            if c in (a, b):
                continue
            dac = D[key(a, c)]
            dbc = D[key(b, c)]
            D[key(new, c)] = (sa * dac + sb * dbc) / (sa + sb)
        active.remove(a)
        active.remove(b)
        active.append(new)

    # leaf order from the merge tree (recursive, left then right)
    def leaves_of(node: int) -> List[int]:
        return members[node]

    root = active[0]
    leaf_order = leaves_of(root)
    return np.array(linkage, dtype=float), leaf_order


def flat_clusters(linkage: np.ndarray, n_leaves: int, threshold: float) -> List[int]:
    """
    Cut the dendrogram at ``threshold``: merge nodes joined below the threshold,
    returning a cluster id (0-based, contiguous) per original leaf.
    """
    if n_leaves == 0:
        return []
    parent = list(range(n_leaves + len(linkage)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i, row in enumerate(linkage):
        a, b, height = int(row[0]), int(row[1]), row[2]
        new = n_leaves + i
        if height <= threshold:
            union(a, new)
            union(b, new)

    # map each leaf's root to a contiguous cluster id
    roots = [find(i) for i in range(n_leaves)]
    remap: Dict[int, int] = {}
    out = []
    for r in roots:
        if r not in remap:
            remap[r] = len(remap)
        out.append(remap[r])
    return out


@dataclass
class DendrogramLayout:
    """Coordinates for drawing a dendrogram."""
    leaf_order: List[int] = field(default_factory=list)
    leaf_x: Dict[int, float] = field(default_factory=dict)   # leaf id -> x
    # each link: (x0, x1, y0, y1) segments forming the bracket
    segments: List[Tuple[float, float, float, float]] = field(default_factory=list)
    node_x: Dict[int, float] = field(default_factory=dict)
    node_y: Dict[int, float] = field(default_factory=dict)


def dendrogram_layout(linkage: np.ndarray, leaf_order: List[int]) -> DendrogramLayout:
    """Compute x/y coordinates + bracket segments for a horizontal-leaf dendrogram."""
    layout = DendrogramLayout(leaf_order=list(leaf_order))
    n = len(leaf_order)
    # leaves on the x-axis at integer positions, y=0
    for pos, leaf in enumerate(leaf_order):
        layout.leaf_x[leaf] = float(pos)
        layout.node_x[leaf] = float(pos)
        layout.node_y[leaf] = 0.0

    for i, row in enumerate(linkage):
        a, b, height = int(row[0]), int(row[1]), float(row[2])
        new = n + i
        xa, xb = layout.node_x[a], layout.node_x[b]
        ya, yb = layout.node_y[a], layout.node_y[b]
        xnew = (xa + xb) / 2.0
        layout.node_x[new] = xnew
        layout.node_y[new] = height
        # bracket: up from a, across at height, down to b
        layout.segments.append((xa, xa, ya, height))   # left vertical
        layout.segments.append((xb, xb, yb, height))   # right vertical
        layout.segments.append((xa, xb, height, height))  # horizontal top
    return layout
