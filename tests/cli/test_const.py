"""Unit tests for eeroctl.const.

Tests cover:
- GENERIC_RENDER_SENSITIVE_KEY_PATTERNS parity with the SDK's own
  eero.logging._ZERO_VISIBILITY_PATTERNS (minus the documented exclusions)
"""

from eero.logging import _ZERO_VISIBILITY_PATTERNS

from eeroctl.const import (
    GENERIC_RENDER_CONTACT_INFO_KEY_PATTERNS,
    GENERIC_RENDER_EXCLUDED_KEY_PATTERNS,
    GENERIC_RENDER_SENSITIVE_KEY_PATTERNS,
)


class TestGenericRenderSensitiveKeyPatternsParity:
    """Every SDK pattern except the three documented exclusions must be present."""

    def test_every_sdk_pattern_is_covered_except_exclusions(self):
        expected = _ZERO_VISIBILITY_PATTERNS - GENERIC_RENDER_EXCLUDED_KEY_PATTERNS
        missing = expected - set(GENERIC_RENDER_SENSITIVE_KEY_PATTERNS)
        assert not missing, f"SDK patterns missing from eeroctl's set: {missing}"

    def test_exclusions_are_not_in_the_final_set(self):
        for excluded in GENERIC_RENDER_EXCLUDED_KEY_PATTERNS:
            assert excluded not in GENERIC_RENDER_SENSITIVE_KEY_PATTERNS

    def test_contact_info_patterns_are_included(self):
        for pattern in GENERIC_RENDER_CONTACT_INFO_KEY_PATTERNS:
            assert pattern in GENERIC_RENDER_SENSITIVE_KEY_PATTERNS

    def test_previously_missing_patterns_now_present(self):
        """Regression test for the batch-2 security review finding.

        `session` (-> `session_id`, the SDK's own bearer-token field),
        `credential`, `passwd`, `bearer`, `private`, `auth` were missing
        from the hand-maintained literal tuple.
        """
        for pattern in ("session", "credential", "passwd", "bearer", "private", "auth"):
            assert pattern in GENERIC_RENDER_SENSITIVE_KEY_PATTERNS

    def test_no_duplicates(self):
        patterns = list(GENERIC_RENDER_SENSITIVE_KEY_PATTERNS)
        assert len(patterns) == len(set(patterns))
