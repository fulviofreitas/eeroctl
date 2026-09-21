"""Unit tests for eero.cli.exit_codes module.

Tests cover:
- ExitCode enum values and consistency
- Exit code descriptions mapping
"""

from eeroctl.exit_codes import EXIT_CODE_DESCRIPTIONS, ExitCode


class TestExitCode:
    """Tests for ExitCode enum."""

    def test_success_is_zero(self):
        """Test SUCCESS exit code is 0."""
        assert ExitCode.SUCCESS == 0
        assert int(ExitCode.SUCCESS) == 0

    def test_generic_error_is_one(self):
        """Test GENERIC_ERROR is 1."""
        assert ExitCode.GENERIC_ERROR == 1

    def test_usage_error_is_two(self):
        """Test USAGE_ERROR is 2."""
        assert ExitCode.USAGE_ERROR == 2

    def test_auth_required_is_three(self):
        """Test AUTH_REQUIRED is 3."""
        assert ExitCode.AUTH_REQUIRED == 3

    def test_not_found_is_five(self):
        """Test NOT_FOUND is 5."""
        assert ExitCode.NOT_FOUND == 5

    def test_safety_rail_is_eight(self):
        """Test SAFETY_RAIL is 8."""
        assert ExitCode.SAFETY_RAIL == 8

    def test_premium_required_is_eleven(self):
        """Test PREMIUM_REQUIRED is 11."""
        assert ExitCode.PREMIUM_REQUIRED == 11

    def test_feature_unavailable_is_twelve(self):
        """Test FEATURE_UNAVAILABLE is 12."""
        assert ExitCode.FEATURE_UNAVAILABLE == 12

    def test_client_blocked_is_thirteen(self):
        """Test CLIENT_BLOCKED is 13 (new in the v8 migration, §2.6)."""
        assert ExitCode.CLIENT_BLOCKED == 13

    def test_network_error_is_fourteen(self):
        """Test NETWORK_ERROR is 14 (new in the v8 migration, §2.6)."""
        assert ExitCode.NETWORK_ERROR == 14

    def test_nine_is_reserved(self):
        """9 stays reserved: no member of the enum may take that value."""
        assert 9 not in {code.value for code in ExitCode}

    def test_all_codes_are_integers(self):
        """Test all exit codes are integers."""
        for code in ExitCode:
            assert isinstance(code.value, int)

    def test_codes_are_unique(self):
        """Test all exit codes have unique values."""
        values = [code.value for code in ExitCode]
        assert len(values) == len(set(values)), "Exit codes must be unique"

    def test_codes_are_in_valid_range(self):
        """Test all exit codes are in valid range (0-255)."""
        for code in ExitCode:
            assert 0 <= code.value <= 255, f"{code.name} out of range"

    def test_codes_are_positive(self):
        """Test all exit codes are non-negative."""
        for code in ExitCode:
            assert code.value >= 0


class TestExitCodeTable:
    """The full 3.0.0 exit-code table (v8 migration plan §2.6)."""

    EXPECTED = {
        0: "SUCCESS",
        1: "GENERIC_ERROR",
        2: "USAGE_ERROR",
        3: "AUTH_REQUIRED",
        4: "FORBIDDEN",
        5: "NOT_FOUND",
        6: "CONFLICT",
        7: "TIMEOUT",
        8: "SAFETY_RAIL",
        10: "PARTIAL_SUCCESS",
        11: "PREMIUM_REQUIRED",
        12: "FEATURE_UNAVAILABLE",
        13: "CLIENT_BLOCKED",
        14: "NETWORK_ERROR",
    }

    def test_table_matches_the_plan_exactly(self):
        """Every code in the plan's table exists with the right name, and no
        other codes exist (9 stays reserved, no stray members)."""
        actual = {code.value: code.name for code in ExitCode}
        assert actual == self.EXPECTED


class TestExitCodeDescriptions:
    """Tests for exit code descriptions mapping."""

    def test_all_codes_have_descriptions(self):
        """Test every exit code has a description."""
        for code in ExitCode:
            assert code in EXIT_CODE_DESCRIPTIONS, f"Missing description for {code.name}"

    def test_descriptions_are_non_empty(self):
        """Test all descriptions are non-empty strings."""
        for code, description in EXIT_CODE_DESCRIPTIONS.items():
            assert isinstance(description, str), f"Description for {code.name} is not a string"
            assert len(description) > 0, f"Description for {code.name} is empty"

    def test_no_extra_descriptions(self):
        """Test no descriptions exist for non-existent codes."""
        valid_codes = set(ExitCode)
        description_codes = set(EXIT_CODE_DESCRIPTIONS.keys())
        extra = description_codes - valid_codes
        assert len(extra) == 0, f"Extra descriptions for: {extra}"


class TestExitCodeUsability:
    """Tests for exit code usability in CLI context."""

    def test_can_use_as_sys_exit_argument(self):
        """Test exit codes can be used with sys.exit."""

        # Just verify the types are compatible
        code = ExitCode.SUCCESS
        assert isinstance(int(code), int)

        code = ExitCode.GENERIC_ERROR
        assert isinstance(int(code), int)

    def test_can_compare_with_integers(self):
        """Test exit codes can be compared with plain integers."""
        assert ExitCode.SUCCESS == 0
        assert ExitCode.GENERIC_ERROR == 1
        assert ExitCode.NOT_FOUND == 5

    def test_exit_codes_sortable(self):
        """Test exit codes are sortable by value."""
        codes = list(ExitCode)
        sorted_codes = sorted(codes, key=lambda c: c.value)

        # SUCCESS should be first
        assert sorted_codes[0] == ExitCode.SUCCESS

    def test_exit_code_representation(self):
        """Test exit codes have useful string representation."""
        code = ExitCode.AUTH_REQUIRED

        # Should include the name
        assert "AUTH_REQUIRED" in repr(code) or "AUTH_REQUIRED" in str(code)
