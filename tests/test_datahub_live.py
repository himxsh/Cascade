import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cascade.datahub_fixture import load_catalog
from cascade.datahub_live import (
    _graphql,
    fetch_dataset,
    fetch_downstream_lineage,
    health_check,
    load_catalog_live,
    resolve_catalog,
)

FIXTURE = Path(__file__).resolve().parents[1] / "demo" / "fixtures" / "demo_graph.json"
RAW_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"
STG_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)"
FCT_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)"


def _mock_response(data: object, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status = status
    m.read.return_value = json.dumps(data).encode()
    m.__enter__.return_value = m
    return m


class TestGraphQLClient(unittest.TestCase):
    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_graphql_success(self, mock_req, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"data": {"dataset": {"urn": RAW_URN}}})
        result = _graphql("http://fake:8080", "query { dataset { urn } }")
        self.assertEqual(result["data"]["dataset"]["urn"], RAW_URN)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_graphql_errors_raises(self, mock_req, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"errors": [{"message": "not found"}]})
        with self.assertRaises(ValueError, msg="not found"):
            _graphql("http://fake:8080", "query { dataset { urn } }")


class TestHealthCheck(unittest.TestCase):
    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_healthy(self, mock_req, mock_urlopen):
        mock_urlopen.return_value = _mock_response({}, status=200)
        self.assertTrue(health_check("http://fake:8080"))

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_unhealthy_status(self, mock_req, mock_urlopen):
        mock_urlopen.return_value = _mock_response({}, status=503)
        self.assertFalse(health_check("http://fake:8080"))

    @patch("urllib.request.urlopen", side_effect=ConnectionError("refused"))
    @patch("urllib.request.Request")
    def test_connection_error(self, mock_req, mock_urlopen):
        self.assertFalse(health_check("http://fake:9999"))


class TestFetchDataset(unittest.TestCase):
    @patch("cascade.datahub_live._graphql")
    def test_fetch_dataset_parses(self, mock_gql):
        mock_gql.return_value = {
            "data": {
                "dataset": {
                    "urn": RAW_URN,
                    "properties": {"name": "raw_orders", "description": ""},
                    "schemaMetadata": {
                        "fields": [
                            {"fieldPath": "order_id", "nativeDataType": "int"},
                            {"fieldPath": "user_id", "nativeDataType": "int"},
                        ]
                    },
                    "ownership": {
                        "owners": [{"owner": {"urn": "urn:li:corpuser:alice"}}]
                    },
                }
            }
        }
        result = fetch_dataset(RAW_URN, "http://fake:8080")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "raw_orders")
        self.assertEqual(len(result["schema_fields"]), 2)
        self.assertEqual(result["schema_fields"][0]["name"], "order_id")
        self.assertEqual(result["owners"], ["urn:li:corpuser:alice"])

    @patch("cascade.datahub_live._graphql")
    def test_fetch_dataset_not_found(self, mock_gql):
        mock_gql.return_value = {"data": {"dataset": None}}
        result = fetch_dataset("urn:li:dataset:nonexistent", "http://fake:8080")
        self.assertIsNone(result)

    @patch("cascade.datahub_live._graphql")
    def test_fetch_dataset_no_schema(self, mock_gql):
        mock_gql.return_value = {
            "data": {"dataset": {"urn": RAW_URN, "properties": {"name": "test"}}}
        }
        result = fetch_dataset(RAW_URN, "http://fake:8080")
        self.assertEqual(result["schema_fields"], [])
        self.assertEqual(result["owners"], [])


class TestFetchLineage(unittest.TestCase):
    @patch("cascade.datahub_live._graphql")
    def test_fetch_downstream_lineage(self, mock_gql):
        mock_gql.return_value = {
            "data": {
                "lineage": {
                    "relationships": [
                        {"entity": {"urn": STG_URN, "properties": {"name": "stg_orders"}}}
                    ]
                }
            }
        }
        urns = fetch_downstream_lineage(RAW_URN, "http://fake:8080")
        self.assertEqual(urns, [STG_URN])

    @patch("cascade.datahub_live._graphql")
    def test_fetch_downstream_lineage_empty(self, mock_gql):
        mock_gql.return_value = {"data": {"lineage": {"relationships": []}}}
        urns = fetch_downstream_lineage(RAW_URN, "http://fake:8080")
        self.assertEqual(urns, [])

    @patch("cascade.datahub_live._graphql")
    def test_fetch_downstream_lineage_pagination(self, mock_gql):
        mock_gql.side_effect = [
            {
                "data": {
                    "lineage": {
                        "relationships": [
                            {"entity": {"urn": STG_URN}}
                        ] * 100
                    }
                }
            },
            {
                "data": {
                    "lineage": {
                        "relationships": [
                            {"entity": {"urn": FCT_URN}}
                        ]
                    }
                }
            },
        ]
        urns = fetch_downstream_lineage(RAW_URN, "http://fake:8080")
        self.assertEqual(len(urns), 101)


class TestLoadCatalogLive(unittest.TestCase):
    def _mock_graphql_hops(self, hops: dict[str, list[str]]) -> None:
        """Mock _graphql to simulate multi-hop lineage + dataset responses."""
        patcher = patch("cascade.datahub_live._graphql")
        mock_gql = patcher.start()
        self.addCleanup(patcher.stop)

        lineage_variable_id = [0]

        def side_effect(url, query, variables, token):
            if "getLineage" in query:
                urn = variables["urn"]
                children = hops.get(urn, [])
                return {
                    "data": {
                        "lineage": {
                            "relationships": [
                                {"entity": {"urn": c}} for c in children
                            ]
                        }
                    }
                }
            if "getDataset" in query:
                urn = variables["urn"]
                return {
                    "data": {
                        "dataset": {
                            "urn": urn,
                            "properties": {"name": urn.split(",")[1].rstrip(")") if "," in urn else urn},
                            "schemaMetadata": {"fields": [{"fieldPath": "col1", "nativeDataType": "int"}]},
                            "ownership": {"owners": []},
                        }
                    }
                }
            return {"data": {}}

        mock_gql.side_effect = side_effect

    def test_load_catalog_live_single_hop(self):
        self._mock_graphql_hops({RAW_URN: [STG_URN], STG_URN: []})
        catalog = load_catalog_live(RAW_URN, "http://fake:8080")
        self.assertIn(RAW_URN, catalog["datasets_by_urn"])
        self.assertIn(STG_URN, catalog["datasets_by_urn"])
        self.assertEqual(catalog["downstream_map"].get(RAW_URN), [STG_URN])
        self.assertEqual(len(catalog["datasets_by_urn"]), 2)

    def test_load_catalog_live_multi_hop_bfs(self):
        self._mock_graphql_hops({RAW_URN: [STG_URN], STG_URN: [FCT_URN], FCT_URN: []})
        catalog = load_catalog_live(RAW_URN, "http://fake:8080")
        self.assertIn(RAW_URN, catalog["datasets_by_urn"])
        self.assertIn(STG_URN, catalog["datasets_by_urn"])
        self.assertIn(FCT_URN, catalog["datasets_by_urn"])
        self.assertEqual(catalog["downstream_map"][RAW_URN], [STG_URN])
        self.assertEqual(catalog["downstream_map"][STG_URN], [FCT_URN])

    def test_load_catalog_live_no_lineage(self):
        self._mock_graphql_hops({RAW_URN: []})
        catalog = load_catalog_live(RAW_URN, "http://fake:8080")
        self.assertEqual(len(catalog["datasets_by_urn"]), 1)
        self.assertEqual(catalog["downstream_map"], {})

    def test_load_catalog_live_hybrid_ml_fixture(self):
        self._mock_graphql_hops({RAW_URN: []})
        catalog = load_catalog_live(RAW_URN, "http://fake:8080", fixture_path=str(FIXTURE))
        self.assertIn("user_id", catalog["ml_features_by_name"])
        self.assertIn("urn:li:mlFeature:(analytics.features_orders,user_id)", catalog["ml_models_by_feature_urn"])
        self.assertEqual(len(catalog["all_ml_features"]), 1)
        self.assertEqual(len(catalog["all_ml_models"]), 1)

    def test_load_catalog_live_hybrid_empty_fixture_path(self):
        self._mock_graphql_hops({RAW_URN: []})
        catalog = load_catalog_live(RAW_URN, "http://fake:8080", fixture_path="/nonexistent/fixture.json")
        self.assertEqual(catalog["ml_features_by_name"], {})
        self.assertEqual(catalog["ml_models_by_feature_urn"], {})


class TestResolveCatalog(unittest.TestCase):
    @patch("cascade.datahub_live.health_check", return_value=True)
    @patch("cascade.datahub_live.load_catalog_live")
    def test_resolve_live_healthy(self, mock_live, mock_health):
        mock_live.return_value = {"_source": "live"}
        catalog = resolve_catalog("live", seed_urn=RAW_URN, fixture_path=str(FIXTURE))
        self.assertEqual(catalog["_source"], "live")

    @patch("cascade.datahub_live.health_check", return_value=False)
    def test_resolve_live_unhealthy_exits(self, mock_health):
        with self.assertRaises(SystemExit):
            resolve_catalog("live", seed_urn=RAW_URN, fixture_path=str(FIXTURE))

    @patch("cascade.datahub_live.health_check", side_effect=[True, False])
    @patch("cascade.datahub_live.load_catalog_live")
    @patch("cascade.datahub_live.load_catalog")
    def test_resolve_auto_prefers_live(self, mock_fallback, mock_live, mock_health):
        mock_live.return_value = {"_source": "live"}
        catalog = resolve_catalog("auto", seed_urn=RAW_URN, fixture_path=str(FIXTURE))
        self.assertEqual(catalog["_source"], "live")
        mock_fallback.assert_not_called()

    @patch("cascade.datahub_live.health_check", side_effect=[False])
    @patch("cascade.datahub_live.load_catalog")
    def test_resolve_auto_falls_back(self, mock_fallback, mock_health):
        mock_fallback.return_value = {"_source": "fixture"}
        catalog = resolve_catalog("auto", seed_urn=RAW_URN, fixture_path=str(FIXTURE))
        self.assertEqual(catalog["_source"], "fixture")
        mock_fallback.assert_called_once_with(str(FIXTURE))

    @patch("cascade.datahub_live.load_catalog")
    def test_resolve_fixture_uses_fixture(self, mock_fallback):
        mock_fallback.return_value = {"_source": "fixture"}
        catalog = resolve_catalog("fixture", seed_urn=RAW_URN, fixture_path=str(FIXTURE))
        self.assertEqual(catalog["_source"], "fixture")


if __name__ == "__main__":
    unittest.main()
