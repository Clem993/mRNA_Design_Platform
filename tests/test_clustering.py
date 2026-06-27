"""Tests for sequence clustering and dendrogram building."""
import numpy as np
import pytest

from core.analysis.clustering import (
    kmer_distance_matrix, upgma, flat_clusters, dendrogram_layout,
)


class TestDistance:
    def test_identical_sequences_zero_distance(self):
        d = kmer_distance_matrix(["ATGCATGC", "ATGCATGC"], k=3)
        assert d[0, 1] == pytest.approx(0.0, abs=1e-9)

    def test_disjoint_sequences_high_distance(self):
        d = kmer_distance_matrix(["AAAAAAAA", "GGGGGGGG"], k=3)
        assert d[0, 1] > 0.9

    def test_matrix_is_symmetric_zero_diagonal(self):
        d = kmer_distance_matrix(["ATGCATGC", "TTGGCCAA", "ATGCATGG"], k=3)
        assert np.allclose(d, d.T)
        assert np.allclose(np.diag(d), 0.0)

    def test_short_sequence_safe(self):
        d = kmer_distance_matrix(["AT", "ATGC"], k=4)  # first too short for k
        assert d.shape == (2, 2)


class TestUPGMA:
    SEQS = ["ATGCATGCATGC", "ATGCATGCATGG", "TTTTGGGGTTTT", "TTTTGGGGTTTG"]

    def test_linkage_shape(self):
        link, order = upgma(kmer_distance_matrix(self.SEQS, k=3))
        assert link.shape == (3, 4)              # n-1 merges
        assert sorted(order) == [0, 1, 2, 3]     # leaf order is a permutation

    def test_single_sequence_safe(self):
        link, order = upgma(kmer_distance_matrix(["ATGC"], k=3))
        assert link.shape == (0, 4)
        assert order == [0]


class TestFlatClusters:
    SEQS = ["ATGCATGCATGC", "ATGCATGCATGG", "TTTTGGGGTTTT", "TTTTGGGGTTTG"]

    def _link(self):
        return upgma(kmer_distance_matrix(self.SEQS, k=3))[0]

    def test_two_clusters_group_correctly(self):
        cl = flat_clusters(self._link(), 4, threshold=0.5)
        assert cl[0] == cl[1] and cl[2] == cl[3] and cl[0] != cl[2]

    def test_high_threshold_single_cluster(self):
        cl = flat_clusters(self._link(), 4, threshold=10.0)
        assert len(set(cl)) == 1

    def test_negative_threshold_all_singletons(self):
        cl = flat_clusters(self._link(), 4, threshold=-1.0)
        assert len(set(cl)) == 4

    def test_cluster_ids_contiguous_from_zero(self):
        cl = flat_clusters(self._link(), 4, threshold=0.5)
        assert set(cl) == set(range(len(set(cl))))


class TestDendrogramLayout:
    def test_segments_and_heights(self):
        seqs = ["ATGCATGCATGC", "ATGCATGCATGG", "TTTTGGGGTTTT", "TTTTGGGGTTTG"]
        link, order = upgma(kmer_distance_matrix(seqs, k=3))
        lay = dendrogram_layout(link, order)
        assert len(lay.segments) == 3 * 3          # 3 segments per merge
        assert all(y >= 0 for y in lay.node_y.values())
        assert len(lay.leaf_x) == 4
