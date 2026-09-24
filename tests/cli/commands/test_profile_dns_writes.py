"""Unit tests for `profile dns allow|block`.

Migration plan §4 phase C row 41 -- premium, MEDIUM + unverified.
Mocks at the SDK boundary (`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli

_PROFILES_RESPONSE = {
    "meta": {"code": 200},
    "data": [{"url": "/2.2/networks/net1/profiles/p1", "name": "Kids"}],
}


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestProfileDnsAllow:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_profile_not_found(self, runner: CliRunner) -> None:
        mock_client = _client(get_profiles={"meta": {"code": 200}, "data": []})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["profile", "dns", "allow", "NoSuchProfile", "example.com", "--force"],
            )

        assert result.exit_code == ExitCode.NOT_FOUND

    def test_allows_domain(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            allow_domain_for_profiles={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "dns", "allow", "Kids", "example.com", "--force"]
            )

        assert result.exit_code == 0
        mock_client.allow_domain_for_profiles.assert_awaited_once_with(
            "example.com", None, profiles=["p1"], override=None, is_delete=None
        )

    def test_override_and_delete_flags_passed_through(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            allow_domain_for_profiles={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "profile",
                    "dns",
                    "allow",
                    "Kids",
                    "example.com",
                    "--override",
                    "--delete",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.allow_domain_for_profiles.assert_awaited_once_with(
            "example.com", None, profiles=["p1"], override=True, is_delete=True
        )

    def test_premium_required_maps_to_exit_code(self, runner: CliRunner) -> None:
        mock_client = _client(get_profiles=_PROFILES_RESPONSE)
        mock_client.allow_domain_for_profiles = AsyncMock(
            side_effect=EeroPremiumRequiredException("premium plan required")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "dns", "allow", "Kids", "example.com", "--force"]
            )

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client(get_profiles=_PROFILES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "profile", "dns", "allow", "Kids", "example.com"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.allow_domain_for_profiles.assert_not_called()


class TestProfileDnsBlock:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_blocks_domain(self, runner: CliRunner) -> None:
        mock_client = _client(
            get_profiles=_PROFILES_RESPONSE,
            block_domain_for_profiles={"meta": {"code": 200}},
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "dns", "block", "Kids", "example.com", "--force"]
            )

        assert result.exit_code == 0
        mock_client.block_domain_for_profiles.assert_awaited_once_with(
            "example.com", None, profiles=["p1"], override=None, is_delete=None
        )

    def test_premium_required_maps_to_exit_code(self, runner: CliRunner) -> None:
        mock_client = _client(get_profiles=_PROFILES_RESPONSE)
        mock_client.block_domain_for_profiles = AsyncMock(
            side_effect=EeroPremiumRequiredException("premium plan required")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["profile", "dns", "block", "Kids", "example.com", "--force"]
            )

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED
