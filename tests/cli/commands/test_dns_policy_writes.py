"""Unit tests for `network dns policy allow|block|allow-cnames`.

Migration plan §4 phase C row 41. Mocks at the SDK boundary
(`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestDnsPolicyAllow:
    # No skip-unchanged test here: `allow_domain` is an additive write with
    # no matching read to compare against (there is no "get the current
    # allowlist" call this command reads before writing), so the
    # read-then-compare skip-unchanged pattern used elsewhere in this suite
    # (e.g. wpa3 per-band, fast-transition) does not apply to this command.

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "dns", "policy", "allow", "--help"])

        assert result.exit_code == 0
        assert "--delete" in result.output
        assert "--keep-profiles" in result.output

    def test_allows_domain(self, runner: CliRunner) -> None:
        mock_client = _client(allow_domain={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "dns", "policy", "allow", "example.com", "--force"]
            )

        assert result.exit_code == 0
        mock_client.allow_domain.assert_awaited_once_with(
            "example.com", None, is_delete=None, keep_profiles=None
        )

    def test_delete_and_keep_profiles_forwarded(self, runner: CliRunner) -> None:
        mock_client = _client(allow_domain={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dns",
                    "policy",
                    "allow",
                    "example.com",
                    "--delete",
                    "--keep-profiles",
                    "p1",
                    "--keep-profiles",
                    "p2",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.allow_domain.assert_awaited_once_with(
            "example.com", None, is_delete=True, keep_profiles=["p1", "p2"]
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "dns", "policy", "allow", "example.com"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.allow_domain.assert_not_called()

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner) -> None:
        mock_client = _client()
        mock_client.allow_domain = AsyncMock(side_effect=EeroPremiumRequiredException("DNS policy"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "dns", "policy", "allow", "example.com", "--force"]
            )

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestDnsPolicyBlock:
    # No skip-unchanged test here either, for the same reason as
    # TestDnsPolicyAllow above: `block_domain` is an additive write with no
    # matching read to compare against.

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_blocks_domain(self, runner: CliRunner) -> None:
        mock_client = _client(block_domain={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "dns", "policy", "block", "example.com", "--force"]
            )

        assert result.exit_code == 0
        mock_client.block_domain.assert_awaited_once_with(
            "example.com", None, is_delete=None, keep_profiles=None
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "dns", "policy", "block", "example.com"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.block_domain.assert_not_called()

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner) -> None:
        mock_client = _client()
        mock_client.block_domain = AsyncMock(side_effect=EeroPremiumRequiredException("DNS policy"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "dns", "policy", "block", "example.com", "--force"]
            )

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED


class TestDnsPolicyAllowCnames:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_at_least_one_domain(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "dns", "policy", "allow-cnames", "--force"])

        assert result.exit_code != 0

    def test_allows_cnames(self, runner: CliRunner) -> None:
        mock_client = _client(allow_cnames={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "dns",
                    "policy",
                    "allow-cnames",
                    "a.example.com",
                    "b.example.com",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.allow_cnames.assert_awaited_once_with(["a.example.com", "b.example.com"], None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "dns",
                    "policy",
                    "allow-cnames",
                    "a.example.com",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.allow_cnames.assert_not_called()
