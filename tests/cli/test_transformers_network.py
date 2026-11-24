"""Tests for network transformers."""

from eeroctl.transformers.network import normalize_network


class TestNormalizeNetworkId:
    def test_int_id_is_coerced_to_str(self):
        # The eero API returns the network detail "id" as an int; Rich tables
        # reject non-string cells, so the normalizer must stringify it.
        assert normalize_network({"id": 12345})["id"] == "12345"

    def test_str_id_is_preserved(self):
        assert normalize_network({"id": "12345"})["id"] == "12345"

    def test_id_falls_back_to_url(self):
        assert normalize_network({"url": "/2.2/networks/9876"})["id"] == "9876"
