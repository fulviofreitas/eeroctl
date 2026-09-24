"""Unit tests for `network members invite|promote|remove-admin|cancel-pending-admin`.

Migration plan §4 phase C, `network members invite create` row. Mocks at the
SDK boundary (`patch("eeroctl.utils.EeroClient", ...)`).
"""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli


def _client(**method_return_values) -> AsyncMock:
    client = AsyncMock()
    for name, value in method_return_values.items():
        setattr(client, name, AsyncMock(return_value=value))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestInviteCreate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "members", "invite", "create", "--help"])

        assert result.exit_code == 0
        assert "--role" in result.output

    def test_requires_role(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "members", "invite", "create", "--force"])

        assert result.exit_code != 0

    def test_invalid_role_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "members", "invite", "create", "--role", "bogus"])

        assert result.exit_code != 0

    def test_creates_invite(self, runner: CliRunner) -> None:
        mock_client = _client(create_invite={"meta": {"code": 201}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "members", "invite", "create", "--role", "admin", "--force"]
            )

        assert result.exit_code == 0
        mock_client.create_invite.assert_awaited_once_with(role="admin", network_id=None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["--non-interactive", "network", "members", "invite", "create", "--role", "admin"],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.create_invite.assert_not_called()


class TestInviteUpdate:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_updates_nickname(self, runner: CliRunner) -> None:
        mock_client = _client(update_invite={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "network",
                    "members",
                    "invite",
                    "update",
                    "inv1",
                    "--nickname",
                    "New nickname",
                    "--force",
                ],
            )

        assert result.exit_code == 0
        mock_client.update_invite.assert_awaited_once_with(
            "inv1", invite_nickname="New nickname", network_id=None
        )

    def test_requires_nickname(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["network", "members", "invite", "update", "inv1", "--force"])

        assert result.exit_code != 0

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "members",
                    "invite",
                    "update",
                    "inv1",
                    "--nickname",
                    "New",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.update_invite.assert_not_called()


class TestInviteDelete:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_deletes_invite(self, runner: CliRunner) -> None:
        mock_client = _client(delete_invite={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "members", "invite", "delete", "inv1", "--force"]
            )

        assert result.exit_code == 0
        mock_client.delete_invite.assert_awaited_once_with("inv1", network_id=None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "members", "invite", "delete", "inv1"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.delete_invite.assert_not_called()


class TestInviteRespond:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_accept_or_decline(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "members", "invite", "respond", "inv1", "--force"]
            )

        assert result.exit_code == ExitCode.USAGE_ERROR
        mock_client.respond_to_invite.assert_not_called()

    def test_accepts(self, runner: CliRunner) -> None:
        mock_client = _client(respond_to_invite={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "members", "invite", "respond", "inv1", "--accept", "--force"],
            )

        assert result.exit_code == 0
        mock_client.respond_to_invite.assert_awaited_once_with(
            accept=True, invite_id="inv1", network_id=None
        )

    def test_declines(self, runner: CliRunner) -> None:
        mock_client = _client(respond_to_invite={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                ["network", "members", "invite", "respond", "inv1", "--decline", "--force"],
            )

        assert result.exit_code == 0
        mock_client.respond_to_invite.assert_awaited_once_with(
            accept=False, invite_id="inv1", network_id=None
        )

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "--non-interactive",
                    "network",
                    "members",
                    "invite",
                    "respond",
                    "inv1",
                    "--accept",
                ],
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.respond_to_invite.assert_not_called()


class TestMembersPromote:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_promotes_member(self, runner: CliRunner) -> None:
        mock_client = _client(promote_member={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "promote", "mem1", "--force"])

        assert result.exit_code == 0
        mock_client.promote_member.assert_awaited_once_with("mem1", network_id=None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "members", "promote", "mem1"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.promote_member.assert_not_called()


class TestMembersRemoveAdmin:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_requires_remove_phrase(self, runner: CliRunner) -> None:
        mock_client = _client(remove_admin={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "members", "remove-admin", "user1"], input="REMOVE\n"
            )

        assert result.exit_code == 0
        mock_client.remove_admin.assert_awaited_once_with("user1", network_id=None)

    def test_phrase_mismatch_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["network", "members", "remove-admin", "user1"], input="nope\n"
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.remove_admin.assert_not_called()

    def test_force_writes(self, runner: CliRunner) -> None:
        mock_client = _client(remove_admin={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "remove-admin", "user1", "--force"])

        assert result.exit_code == 0
        mock_client.remove_admin.assert_awaited_once_with("user1", network_id=None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "members", "remove-admin", "user1"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.remove_admin.assert_not_called()


class TestCancelPendingAdmin:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_cancels(self, runner: CliRunner) -> None:
        mock_client = _client(cancel_pending_admin={"meta": {"code": 200}, "data": {}})

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "cancel-pending-admin", "--force"])

        assert result.exit_code == 0
        mock_client.cancel_pending_admin.assert_awaited_once_with(None)

    def test_non_interactive_without_force_fails(self, runner: CliRunner) -> None:
        mock_client = _client()

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--non-interactive", "network", "members", "cancel-pending-admin"]
            )

        assert result.exit_code == ExitCode.SAFETY_RAIL
        mock_client.cancel_pending_admin.assert_not_called()
