"""Unit tests for eero.cli.exit_codes module.

Tests cover:
- ExitCode enum values and consistency
- Exit code descriptions mapping
"""

from eero_cli.exit_codes import EXIT_CODE_DESCRIPTIONS, ExitCode


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
