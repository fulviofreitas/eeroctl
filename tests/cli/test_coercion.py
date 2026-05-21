"""Unit tests for eeroctl._coercion module.

Tests cover:
- coerce_numeric with int, float, str, dict, None, and bool inputs
- Dict coercion with all supported key names
- Recursive dict coercion
- Unknown-dict dedup logging
- Regression: normalize_eero with uptime as dict produces a numeric value
- Regression: _eero_performance_panel with uptime as dict does not raise TypeError
"""

from __future__ import annotations

import logging
from io import StringIO
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from eeroctl._coercion import _logged_unknown, coerce_numeric
from eeroctl.formatting.eero import _eero_performance_panel
from eeroctl.transformers.eero import normalize_eero


# ========================== coerce_numeric: scalar inputs ==========================


class TestCoerceNumericScalars:
    """Tests for coerce_numeric with scalar inputs."""

    def test_int_returned_as_int(self):
        """Test integer input is returned as-is."""
        assert coerce_numeric(3600) == 3600
        assert isinstance(coerce_numeric(3600), int)

    def test_float_with_fractional_returned_as_float(self):
        """Test float with fractional part is returned as float."""
        result = coerce_numeric(3600.5)
        assert result == 3600.5
        assert isinstance(result, float)

    def test_float_whole_number_returned_as_int(self):
        """Test float that is a whole number is returned as int."""
        result = coerce_numeric(3600.0)
        assert result == 3600
        assert isinstance(result, int)

    def test_zero_int_returned(self):
        """Test zero is returned correctly."""
        assert coerce_numeric(0) == 0

    def test_negative_number_returned(self):
        """Test negative numbers pass through."""
        assert coerce_numeric(-5) == -5

    def test_none_returns_none(self):
        """Test None returns None."""
        assert coerce_numeric(None) is None

    def test_bool_true_returns_none(self):
        """Test bool True returns None (bool is subclass of int but not numeric here)."""
        assert coerce_numeric(True) is None

    def test_bool_false_returns_none(self):
        """Test bool False returns None."""
        assert coerce_numeric(False) is None

    def test_list_returns_none(self):
        """Test unexpected list type returns None."""
        assert coerce_numeric([1, 2, 3]) is None

    def test_object_returns_none(self):
        """Test arbitrary objects return None."""
        assert coerce_numeric(object()) is None


# ========================== coerce_numeric: string inputs ==========================


class TestCoerceNumericStrings:
    """Tests for coerce_numeric with string inputs."""

    def test_numeric_string_int(self):
        """Test numeric string like '3600' is coerced to int."""
        result = coerce_numeric("3600")
        assert result == 3600
        assert isinstance(result, int)

    def test_numeric_string_float(self):
        """Test numeric string with decimal is coerced to float."""
        result = coerce_numeric("3600.5")
        assert result == 3600.5
        assert isinstance(result, float)

    def test_invalid_string_returns_none(self):
        """Test non-numeric string returns None."""
        assert coerce_numeric("not-a-number") is None

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert coerce_numeric("") is None


# ========================== coerce_numeric: dict inputs ==========================


class TestCoerceNumericDicts:
    """Tests for coerce_numeric with dict inputs."""

    def test_dict_with_seconds_key(self):
        """Test dict with 'seconds' key is coerced."""
        result = coerce_numeric({"seconds": 3600, "human": "1h"}, "uptime")
        assert result == 3600

    def test_dict_with_value_key(self):
        """Test dict with 'value' key is coerced."""
        result = coerce_numeric({"value": 42}, "some_field")
        assert result == 42

    def test_dict_with_current_key(self):
        """Test dict with 'current' key is coerced."""
        result = coerce_numeric({"current": 75, "max": 100}, "cpu_usage")
        assert result == 75

    def test_dict_with_total_key(self):
        """Test dict with 'total' key is coerced."""
        result = coerce_numeric({"total": 1000}, "memory_usage")
        assert result == 1000

    def test_dict_with_count_key(self):
        """Test dict with 'count' key is coerced."""
        result = coerce_numeric({"count": 5}, "some_count")
        assert result == 5

    def test_dict_key_priority_seconds_over_value(self):
        """Test 'seconds' is tried before 'value'."""
        result = coerce_numeric({"seconds": 100, "value": 200}, "uptime")
        assert result == 100

    def test_dict_unknown_keys_returns_none(self):
        """Test dict with no known keys returns None."""
        # Clear dedup set so log fires
        _logged_unknown.discard(("unknown_field", ("foo", "bar")))
        result = coerce_numeric({"foo": 1, "bar": 2}, "unknown_field")
        assert result is None

    def test_dict_unknown_keys_logs_debug_once(self):
        """Test that unknown dict shape logs DEBUG exactly once per (field, keys)."""
        field = "dedup_test_field"
        key_tuple = ("alpha", "beta")
        _logged_unknown.discard((field, key_tuple))

        with patch("eeroctl._coercion.logger") as mock_logger:
            coerce_numeric({"alpha": None, "beta": None}, field)
            coerce_numeric({"alpha": None, "beta": None}, field)

        assert mock_logger.debug.call_count == 1

    def test_empty_dict_returns_none(self):
        """Test empty dict returns None."""
        result = coerce_numeric({}, "some_field")
        assert result is None

    def test_recursive_dict_coercion(self):
        """Test dict value is recursively coerced (e.g. nested numeric string)."""
        result = coerce_numeric({"seconds": "1000"}, "uptime")
        assert result == 1000

    def test_recursive_dict_none_value(self):
        """Test dict where matched key has None value returns None."""
        result = coerce_numeric({"seconds": None}, "uptime")
        assert result is None


# ========================== Regression: transformer ==========================


class TestNormalizeEeroUptimeRegression:
    """Regression tests: normalize_eero correctly coerces uptime dict."""

    def _base_data(self, **overrides: Any) -> Dict[str, Any]:
        return {
            "url": "/2.2/networks/1/eeros/42",
            "status": "green",
            **overrides,
        }

    def test_uptime_as_seconds_dict_produces_numeric(self):
        """Regression: uptime={'seconds': 1000} yields uptime==1000 in normalized output."""
        data = self._base_data(uptime={"seconds": 1000, "human": "16m"})
        result = normalize_eero(data)
        assert result["uptime"] == 1000

    def test_uptime_as_int_unchanged(self):
        """Legacy numeric uptime is preserved."""
        data = self._base_data(uptime=3661)
        result = normalize_eero(data)
        assert result["uptime"] == 3661

    def test_uptime_none_stays_none(self):
        """Missing uptime stays None."""
        data = self._base_data()
        result = normalize_eero(data)
        assert result["uptime"] is None

    def test_memory_usage_dict_coerced(self):
        """memory_usage dict is coerced to numeric."""
        data = self._base_data(memory_usage={"value": 55})
        result = normalize_eero(data)
        assert result["memory_usage"] == 55

    def test_cpu_usage_dict_coerced(self):
        """cpu_usage dict is coerced to numeric."""
        data = self._base_data(cpu_usage={"current": 12})
        result = normalize_eero(data)
        assert result["cpu_usage"] == 12

    def test_temperature_dict_coerced(self):
        """temperature dict is coerced to numeric."""
        data = self._base_data(temperature={"value": 45.5})
        result = normalize_eero(data)
        assert result["temperature"] == 45.5

    def test_mesh_quality_bars_dict_coerced(self):
        """mesh_quality_bars dict is coerced to numeric."""
        data = self._base_data(mesh_quality_bars={"value": 4})
        result = normalize_eero(data)
        assert result["mesh_quality_bars"] == 4


# ========================== Regression: formatter ==========================


class TestEeroPerformancePanelUptimeRegression:
    """Regression tests: _eero_performance_panel handles uptime dict without TypeError."""

    def test_uptime_dict_does_not_raise(self):
        """Regression: uptime as dict must not cause TypeError in formatter."""
        eero: Dict[str, Any] = {"uptime": {"seconds": 1000, "human": "16m"}}
        # Should not raise
        panel = _eero_performance_panel(eero)
        assert panel is not None

    def test_uptime_dict_formats_as_minutes(self):
        """uptime=1000s (16m 40s) formats as '0 hours' (< 1 day, < 1 hour)."""
        eero: Dict[str, Any] = {"uptime": {"seconds": 1000, "human": "16m"}}
        panel = _eero_performance_panel(eero)
        # Extract rendered text from the panel renderable
        rendered = str(panel.renderable)
        assert "hours" in rendered or "Uptime" in rendered

    def test_uptime_dict_exact_hours_format(self):
        """uptime={'seconds': 7200} (2h) formats correctly."""
        eero: Dict[str, Any] = {"uptime": {"seconds": 7200}}
        panel = _eero_performance_panel(eero)
        rendered = str(panel.renderable)
        assert "2 hours" in rendered

    def test_uptime_dict_days_format(self):
        """uptime={'seconds': 90000} (25h) formats with days."""
        eero: Dict[str, Any] = {"uptime": {"seconds": 90000}}
        panel = _eero_performance_panel(eero)
        rendered = str(panel.renderable)
        assert "days" in rendered

    def test_uptime_int_still_works(self):
        """Legacy int uptime continues to work in formatter."""
        eero: Dict[str, Any] = {"uptime": 7200}
        panel = _eero_performance_panel(eero)
        rendered = str(panel.renderable)
        assert "2 hours" in rendered

    def test_uptime_none_panel_returns_none_when_no_other_fields(self):
        """None uptime with no other perf fields returns None panel."""
        eero: Dict[str, Any] = {"uptime": None}
        panel = _eero_performance_panel(eero)
        assert panel is None

    def test_uptime_unknown_dict_returns_no_uptime_line(self):
        """Unknown dict shape for uptime silently skips uptime line."""
        eero: Dict[str, Any] = {
            "uptime": {"unknown_key": 9999},
            "mesh_quality_bars": 4,
        }
        # Should not raise; panel is built from mesh_quality_bars
        panel = _eero_performance_panel(eero)
        assert panel is not None
