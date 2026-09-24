"""Unit tests for eeroctl.formatting.network.

Tests cover:
- get_network_show_fields(): snapshot of the (label, value) projection used by
  `network show` for both a fully-populated and a minimal network dict
- get_network_list_data(): dict view of the same projection
"""

from eeroctl.formatting.network import get_network_list_data, get_network_show_fields

FULL_NETWORK = {
    "_raw": {},
    "name": "Home",
    "status": "online",
    "public_ip": "203.0.113.7",
    "isp_name": "Example ISP",
    "created_at": "2024-01-02T03:04:05Z",
    "updated_at": "2024-05-06T07:08:09Z",
    "owner": "Alice",
    "network_customer_type": "residential",
    "guest_network_enabled": True,
    "gateway": "eero Pro 6",
    "wan_type": "dhcp",
    "gateway_ip": "192.168.4.1",
    "backup_internet_enabled": True,
    "dhcp": {
        "subnet_mask": "255.255.255.0",
        "starting_address": "",
        "ending_address": "192.168.4.254",
        "lease_time_seconds": 7200,
        "dns_server": None,
    },
    "dns": {
        "mode": "custom",
        "caching": True,
        "parent": {"ips": ["1.1.1.1", "1.0.0.1"]},
        "custom": {"ips": ["9.9.9.9"]},
    },
    "geo_ip": {
        "city": "Lisbon",
        "regionName": "Lisboa",
        "countryCode": "PT",
        "timezone": "Europe/Lisbon",
        "org": "Example Org",
        "asn": 64500,
    },
    "speed_test": {
        "down": {"value": 940.25},
        "up": {"value": 120},
        "latency": {"value": 8},
        "date": "2024-05-06T07:00:00.000Z",
    },
}

FULL_FIELDS = [
    ("Name", "Home"),
    ("Status", "online"),
    ("Public IP", "203.0.113.7"),
    ("ISP", "Example ISP"),
    ("Created", "2024-01-02 03:04:05"),
    ("Updated", "2024-05-06 07:08:09"),
    ("Owner", "Alice"),
    ("Type", "residential"),
    ("Guest Network", "Enabled"),
    ("Gateway Type", "eero Pro 6"),
    ("WAN Type", "dhcp"),
    ("Gateway IP", "192.168.4.1"),
    ("Backup Internet", "Enabled"),
    ("Subnet Mask", "255.255.255.0"),
    ("Starting Address", "Automatic"),
    ("Ending Address", "192.168.4.254"),
    ("Lease Time", "2 hours"),
    ("DNS Server", "Default"),
    ("DNS Mode", "custom"),
    ("DNS Caching", "Enabled"),
    ("Upstream DNS", "1.1.1.1, 1.0.0.1"),
    ("Custom DNS", "9.9.9.9"),
    ("Location", "Lisbon, Lisboa, PT"),
    ("Timezone", "Europe/Lisbon"),
    ("Organization", "Example Org"),
    ("ASN", "AS64500"),
    ("Download", "940.2 Mbps"),
    ("Upload", "120 Mbps"),
    ("Latency", "8 ms"),
    ("Tested", "2024-05-06 07:00:00"),
]

MINIMAL_NETWORK = {
    "_raw": {},
    "name": "Bare",
    "dns": {"mode": "automatic", "parent": None, "custom": "bogus"},
    "geo_ip": {"city": None},
    "speed_test": {"down": None, "up": {"value": 0}, "latency": {}, "date": "Unknown"},
}

MINIMAL_FIELDS = [
    ("Name", "Bare"),
    ("Status", None),
    ("Public IP", None),
    ("ISP", None),
    ("Created", "Unknown"),
    ("Updated", "Unknown"),
    ("Owner", None),
    ("Type", None),
    ("Guest Network", "Disabled"),
    ("Gateway Type", None),
    ("WAN Type", None),
    ("Gateway IP", None),
    ("DNS Mode", "automatic"),
    ("DNS Caching", "Disabled"),
]


class TestGetNetworkShowFields:
    def test_full_network_snapshot(self):
        assert get_network_show_fields(FULL_NETWORK) == FULL_FIELDS

    def test_minimal_network_snapshot(self):
        assert get_network_show_fields(MINIMAL_NETWORK) == MINIMAL_FIELDS

    def test_list_data_mirrors_show_fields(self):
        assert get_network_list_data(FULL_NETWORK) == dict(FULL_FIELDS)
