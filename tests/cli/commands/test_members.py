"""Unit tests for eeroctl.commands.network.members.

Tests cover:
- network members list    (get_members, verified, data.members)
- network members invites (get_invites, unverified; friendly 403 -> exit 4)
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from eero.exceptions import EeroAccessDeniedException, EeroPremiumRequiredException

from eeroctl.exit_codes import ExitCode
from eeroctl.main import cli
from eeroctl.transformers.members import extract_members_list

# Reuse the mock-client helpers defined in test_events.py rather than
# redefining them per module (standing rule from the batch-1 test audit); a
# shared conftest fixture lands after the group-1 stack is pushed.
from .test_events import _mock_client, _mock_client_raising

MEMBERS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"members": [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]},
}
EMPTY_MEMBERS_RESPONSE = {"meta": {"code": 200}, "data": {"members": []}}
INVITES_RESPONSE = {"meta": {"code": 200}, "data": {"invites": [{"id": "inv1"}]}}
EMPTY_RESPONSE = {"meta": {"code": 200}, "data": {}}


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestMembersGroup:
    """Tests for the `network members` command group."""

    def test_members_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "members", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "invites" in result.output


class TestMembersList:
    """Tests for `network members list`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "members", "list", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_members=MEMBERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", output_format, "network", "members", "list"])

        assert result.exit_code == 0
        mock_client.get_members.assert_awaited_once()

    def test_table_output_shows_members(self, runner: CliRunner):
        mock_client = _mock_client(get_members=MEMBERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "list"])

        assert result.exit_code == 0
        assert "Alice" in result.output
        assert "Bob" in result.output

    def test_json_output_passes_full_data_through(self, runner: CliRunner):
        mock_client = _mock_client(get_members=MEMBERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "members", "list"])

        parsed = json.loads(result.output)
        assert parsed["data"] == MEMBERS_RESPONSE["data"]
        assert parsed["schema"] == "eero.network.members.list/v1"

    def test_empty_members(self, runner: CliRunner):
        mock_client = _mock_client(get_members=EMPTY_MEMBERS_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "list"])

        assert result.exit_code == 0

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_members=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "list"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising("get_members", EeroPremiumRequiredException("Members"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "list"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_maps_to_exit_4(self, runner: CliRunner):
        # commit 6 maps EeroAccessDeniedException directly; until then it falls
        # through the generic EeroAPIException branch's status_code == 403 check.
        mock_client = _mock_client_raising(
            "get_members", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "list"])

        assert result.exit_code == ExitCode.FORBIDDEN

    def test_table_shows_dedicated_columns(self, runner: CliRunner):
        """`table` gets a dedicated name/email/role/status view (Low finding,
        batch-2 security review) -- email is shown deliberately here.
        """
        response = {
            "meta": {"code": 200},
            "data": {
                "members": [
                    {
                        "name": "Alice",
                        "email": "alice@example.com",
                        "role": "owner",
                        "status": "active",
                    }
                ]
            },
        }
        mock_client = _mock_client(get_members=response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "list"])

        assert result.exit_code == 0
        assert "Alice" in result.output
        assert "alice@example.com" in result.output
        assert "owner" in result.output
        assert "active" in result.output


class TestMembersListTextRedaction:
    """Regression tests for the batch-2 security review Medium finding.

    `print_members` used to gate on `is_structured_output()` (True for
    json/yaml/text alike), so `--output text` rendered the raw, unredacted
    `data.members` payload -- leaking a planted `invite_token`/`session_id`
    the same way `account premium`/`network events` did before the
    render_generic fix. Only json/yaml may see the raw payload now.
    """

    def test_text_output_redacts_planted_invite_token_and_session_id(self, runner: CliRunner):
        response = {
            "meta": {"code": 200},
            "data": {
                "members": [
                    {
                        "name": "Alice",
                        "invite_token": "SECRETINVITETOKEN",
                        "session_id": "SESSIONSECRET999",
                    }
                ]
            },
        }
        mock_client = _mock_client(get_members=response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "text", "network", "members", "list"])

        assert result.exit_code == 0
        assert "SECRETINVITETOKEN" not in result.output
        assert "SESSIONSECRET999" not in result.output

    def test_json_output_still_carries_the_raw_values(self, runner: CliRunner):
        """json stays the deliberate raw-payload opt-in."""
        response = {
            "meta": {"code": 200},
            "data": {"members": [{"name": "Alice", "invite_token": "SECRETINVITETOKEN"}]},
        }
        mock_client = _mock_client(get_members=response)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "members", "list"])

        parsed = json.loads(result.output)
        assert parsed["data"]["members"][0]["invite_token"] == "SECRETINVITETOKEN"


class TestMembersInvites:
    """Tests for `network members invites`."""

    def test_help(self, runner: CliRunner):
        result = runner.invoke(cli, ["network", "members", "invites", "--help"])

        assert result.exit_code == 0

    @pytest.mark.parametrize("output_format", ["table", "list", "json", "yaml", "text"])
    def test_happy_path_all_formats(self, runner: CliRunner, output_format: str):
        mock_client = _mock_client(get_invites=INVITES_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(
                cli, ["--output", output_format, "network", "members", "invites"]
            )

        assert result.exit_code == 0
        mock_client.get_invites.assert_awaited_once()

    def test_empty_data(self, runner: CliRunner):
        mock_client = _mock_client(get_invites=EMPTY_RESPONSE)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "invites"])

        assert result.exit_code == 0

    def test_premium_required_maps_to_exit_11(self, runner: CliRunner):
        mock_client = _mock_client_raising("get_invites", EeroPremiumRequiredException("Invites"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "invites"])

        assert result.exit_code == ExitCode.PREMIUM_REQUIRED

    def test_access_denied_via_eero_access_denied_exception_is_friendly(self, runner: CliRunner):
        """EeroAccessDeniedException gets the friendly not-permitted message, exit 4."""
        mock_client = _mock_client_raising(
            "get_invites", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "invites"])

        assert result.exit_code == ExitCode.FORBIDDEN
        assert "not permitted" in result.output.lower()

    def test_access_denied_via_403_fallback_is_friendly(self, runner: CliRunner):
        """A generic 403 EeroAPIException also gets the friendly message.

        commit 6 maps EeroAccessDeniedException directly; until then a 403
        surfaces as the generic eero.exceptions.EeroAPIException.
        """
        from eero.exceptions import EeroAPIException

        mock_client = _mock_client_raising("get_invites", EeroAPIException(403, "Forbidden"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "invites"])

        assert result.exit_code == ExitCode.FORBIDDEN
        assert "not permitted" in result.output.lower()

    def test_non_403_api_error_is_not_treated_as_not_permitted(self, runner: CliRunner):
        """A non-403 EeroAPIException is not swallowed by the friendly-message path."""
        from eero.exceptions import EeroAPIException

        mock_client = _mock_client_raising("get_invites", EeroAPIException(500, "Server error"))

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["network", "members", "invites"])

        assert result.exit_code == ExitCode.GENERIC_ERROR
        assert "not permitted" not in result.output.lower()

    def test_json_output_on_403_still_emits_structured_envelope(self, runner: CliRunner):
        mock_client = _mock_client_raising(
            "get_invites", EeroAccessDeniedException(403, "Forbidden")
        )

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "network", "members", "invites"])

        assert result.exit_code == ExitCode.FORBIDDEN
        parsed = json.loads(result.output)
        assert parsed["data"]["error"] == "not_permitted"


class TestExtractMembersList:
    """Unit tests for the `data.members` accessor."""

    def test_extracts_list_from_wrapper_dict(self):
        assert extract_members_list({"members": [{"id": "1"}]}) == [{"id": "1"}]

    def test_returns_empty_list_when_key_missing(self):
        assert extract_members_list({}) == []

    def test_tolerates_bare_list(self):
        assert extract_members_list([{"id": "1"}]) == [{"id": "1"}]

    def test_returns_empty_list_for_non_dict_non_list(self):
        assert extract_members_list(None) == []
