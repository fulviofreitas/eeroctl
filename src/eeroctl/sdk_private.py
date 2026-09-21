"""The only module in eeroctl allowed to touch ``EeroClient._api``.

Every function below reaches into a private attribute of the installed
``eero-api`` SDK because the corresponding operation has no public facade
method: the SDK's public surface is ``EeroClient``, but ``clear_auth_data``,
``resend_verification_code`` and ``reboot_network`` are only reachable
through the internal ``AuthAPI``/``NetworksAPI`` domain classes
(``client._api.auth`` / ``client._api.networks``).

Keeping every such access in one module means a future SDK release that
renames or reshapes one of these methods only requires a change here.  Each
wrapper is exercised by a signature-binding test
(``tests/cli/test_sdk_private.py``) against the domain class it reaches
into, so SDK-internal drift fails CI instead of surfacing as a user-facing
crash. ``grep -rn "_api" src/eeroctl`` should only ever match this file.

See the eero-api v8 migration plan (``.claude/tasks/eero-api-8-migration-plan.md``,
§2.1 and §12 Q8) for the upstream context and the decision to keep these
wrappers here until eero-api exposes public equivalents.
"""

from typing import Any, Dict, Optional

from eero import EeroClient


async def clear_all_credentials(client: EeroClient) -> None:
    """Delete every stored credential for *client*, in every backend.

    Wraps ``AuthAPI.clear_auth_data``, which has no public equivalent: it is
    also the only call that resets the SDK's internal ``_login_in_progress``
    flag alongside the stored record, which is why ``auth login``/``auth
    clear`` reach into it rather than the public ``logout()``.

    Installed eero-api 7.0.0: ``clear_auth_data(self) -> None``
    (``.venv/lib/python3.14/site-packages/eero/api/auth.py:372``).

    Args:
        client: The client whose credentials should be cleared.
    """
    await client._api.auth.clear_auth_data()


async def resend_verification_code(client: EeroClient) -> bool:
    """Resend the login verification code for *client*'s in-progress login.

    Wraps ``AuthAPI.resend_verification_code``, which has no public
    equivalent.

    Installed eero-api 7.0.0: ``resend_verification_code(self) -> bool``
    (``.venv/lib/python3.14/site-packages/eero/api/auth.py:203``).

    Args:
        client: The client with a login flow in progress.

    Returns:
        True if the resend request succeeded.
    """
    return await client._api.auth.resend_verification_code()


async def reboot_network(client: EeroClient, network_id: Optional[str]) -> Dict[str, Any]:
    """Reboot every eero on a network via the network's published reboot link.

    Wraps ``NetworksAPI.reboot_network``, which has no public facade
    equivalent yet (v8 migration plan §12 Q8: an upstream issue requests
    one). Fetches the network's own envelope first, via the public facade,
    so the write can follow the API's published ``reboot`` link rather than
    the default id-based template.

    eero-api v8.0.1: ``reboot_network(self, network_id: str, *, parent:
    Optional[Mapping[str, Any]] = None) -> Dict[str, Any]``
    (``src/eero/api/networks.py:151-153`` in the v8.0.1 tree at
    ``/tmp/eero-api-v8.0.1``).

    Installed eero-api 7.0.0: ``reboot_network(self, network_id: str) ->
    Dict[str, Any]`` -- no ``parent`` keyword yet
    (``.venv/lib/python3.14/site-packages/eero/api/networks.py:134``).

    Not wired to a command in this commit; ``network reboot`` (HIGH tier,
    ``REBOOT`` phrase) lands in a later commit per the v8 migration plan,
    §4 phase C.

    Args:
        client: An authenticated client.
        network_id: A bare network id, path or URL, or None to let the
            facade resolve the preferred network.

    Returns:
        The raw API response envelope.
    """
    envelope = await client.get_network(network_id)
    url = envelope["data"]["url"]
    # The installed eero-api (7.0.0) stub lacks the `parent` kwarg that
    # v8.0.1 adds; mypy checks against whatever is installed, so this call
    # is only fully type-checked once the pin moves to 8.0.1 (see the
    # docstring above for both signatures).
    return await client._api.networks.reboot_network(url, parent=envelope)  # type: ignore[call-arg]
