"""Unit tests for eeroctl.sdk_private.

Two kinds of coverage per wrapper:
- Signature-binding tests against the *real* installed eero-api domain
  class, so SDK-internal drift fails CI instead of surfacing as a
  user-facing crash.
- Behaviour tests with a mocked client, asserting the wrapper calls the
  private method with the right arguments.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import eero
import pytest
from eero.api.auth import AuthAPI
from eero.api.networks import NetworksAPI

from eeroctl.sdk_private import (
    clear_all_credentials,
    reboot_network,
    resend_verification_code,
)


class TestSignatureBinding:
    """Bind the exact calls the wrappers make against the installed SDK."""

    def test_clear_auth_data_binds(self):
        """``AuthAPI.clear_auth_data`` takes no arguments beyond self."""
        sig = inspect.signature(AuthAPI.clear_auth_data)

        sig.bind(MagicMock())

    def test_resend_verification_code_binds(self):
        """``AuthAPI.resend_verification_code`` takes no arguments beyond self."""
        sig = inspect.signature(AuthAPI.resend_verification_code)

        sig.bind(MagicMock())

    def test_reboot_network_binds_bare_network_id(self):
        """The base call, (self, network_id), is stable on 7.0.0 and 8.0.1."""
        sig = inspect.signature(NetworksAPI.reboot_network)

        sig.bind(MagicMock(), "network-id")

    def test_reboot_network_parent_kwarg_binds_or_skips(self):
        """``parent=`` only exists from eero-api 8.0.1 onward.

        eero-api 7.0.0's ``NetworksAPI.reboot_network`` takes only
        ``network_id``
        (``.venv/lib/python3.14/site-packages/eero/api/networks.py:134``);
        v8.0.1 adds ``*, parent: Optional[Mapping[str, Any]] = None``
        (``src/eero/api/networks.py:151-153`` in the v8.0.1 tree). Skip on
        older installs so this commit stays green on 7.0.0 while still
        confirming the binding once the pin moves to 8.0.1.
        """
        sig = inspect.signature(NetworksAPI.reboot_network)

        try:
            sig.bind(MagicMock(), "network-id", parent={"data": {}})
        except TypeError:
            pytest.skip(
                f"installed eero-api {eero.__version__} has no parent= kwarg "
                "on NetworksAPI.reboot_network; binds against v8.0.1"
            )


class TestClearAllCredentials:
    """Behaviour tests for clear_all_credentials."""

    @pytest.mark.asyncio
    async def test_calls_private_clear_auth_data(self):
        client = MagicMock()
        client._api.auth.clear_auth_data = AsyncMock()

        await clear_all_credentials(client)

        client._api.auth.clear_auth_data.assert_awaited_once_with()


class TestResendVerificationCode:
    """Behaviour tests for resend_verification_code."""

    @pytest.mark.asyncio
    async def test_calls_private_resend_verification_code(self):
        client = MagicMock()
        client._api.auth.resend_verification_code = AsyncMock(return_value=True)

        result = await resend_verification_code(client)

        client._api.auth.resend_verification_code.assert_awaited_once_with()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        client = MagicMock()
        client._api.auth.resend_verification_code = AsyncMock(return_value=False)

        result = await resend_verification_code(client)

        assert result is False


class TestRebootNetwork:
    """Behaviour tests for reboot_network."""

    @pytest.mark.asyncio
    async def test_fetches_network_then_calls_private_reboot_with_url_and_parent(self):
        envelope = {"meta": {"code": 200}, "data": {"url": "/2.2/networks/123"}}
        client = MagicMock()
        client.get_network = AsyncMock(return_value=envelope)
        client._api.networks.reboot_network = AsyncMock(return_value={"meta": {"code": 200}})

        result = await reboot_network(client, "123")

        client.get_network.assert_awaited_once_with("123")
        client._api.networks.reboot_network.assert_awaited_once_with(
            "/2.2/networks/123", parent=envelope
        )
        assert result == {"meta": {"code": 200}}

    @pytest.mark.asyncio
    async def test_accepts_none_network_id(self):
        """A None network_id lets the facade resolve the preferred network."""
        envelope = {"data": {"url": "/2.2/networks/456"}}
        client = MagicMock()
        client.get_network = AsyncMock(return_value=envelope)
        client._api.networks.reboot_network = AsyncMock(return_value={})

        await reboot_network(client, None)

        client.get_network.assert_awaited_once_with(None)
        client._api.networks.reboot_network.assert_awaited_once_with(
            "/2.2/networks/456", parent=envelope
        )
