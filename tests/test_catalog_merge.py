import unittest

from cascade.datahub_fixture import merge_catalogs


class TestCatalogMerge(unittest.TestCase):
    def test_merge_catalogs_unions_lineage_and_datasets(self):
        merged = merge_catalogs([
            {"datasets_by_urn": {"a": {"name": "A"}}, "downstream_map": {"a": ["b"]}},
            {"datasets_by_urn": {"c": {"name": "C"}}, "downstream_map": {"a": ["b", "d"]}},
        ])
        self.assertEqual(set(merged["datasets_by_urn"]), {"a", "c"})
        self.assertEqual(merged["downstream_map"], {"a": ["b", "d"]})

    def test_overlapping_lineage_is_ordered_union(self):
        merged = merge_catalogs([{"downstream_map": {"x": ["y"]}}, {"downstream_map": {"x": ["z"]}}])
        self.assertEqual(merged["downstream_map"], {"x": ["y", "z"]})

    def test_datasets_from_catalogs_are_combined(self):
        merged = merge_catalogs([{"datasets_by_urn": {"a": {"name": "A"}}}, {"datasets_by_urn": {"b": {"name": "B"}}}])
        self.assertEqual(merged["datasets_by_urn"], {"a": {"name": "A"}, "b": {"name": "B"}})
