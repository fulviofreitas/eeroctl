"""Safety middleware for the Eero CLI.

Handles confirmation prompts for destructive/disruptive operations.
Provides consistent safety behavior across all mutating commands.

eero-api 8.0.1 write semantics (migration plan §3): every write either
comes back with a live-verified read-back (``WriteStatus.VERIFIED``) or is
only known to have been accepted by the API, with its side effects
uncharacterised against a live network (``WriteStatus.UNVERIFIED``). Some
writes also reboot something -- a single eero, every eero on the network
(mesh), or merely disconnect clients -- independent of whether the write
itself is verified. ``WriteSpec`` captures both axes for every write
command eeroctl exposes; ``WRITE_SPECS`` is the single registry, replacing
the old ``OPERATION_RISKS`` documentation-only mapping. Every command that
calls :func:`require_write_confirmation` looks its tier up here instead of
hard-coding an ``OperationRisk``.
"""

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Literal, Optional

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .exit_codes import ExitCode


class OperationRisk(str, Enum):
    """Risk level of an operation."""

    LOW = "low"
    """Low risk - no confirmation needed."""

    MEDIUM = "medium"
    """Medium risk - simple Y/N confirmation."""

    HIGH = "high"
    """High risk - requires typed confirmation phrase."""


class WriteStatus(str, Enum):
    """How confident eero-api is that a write's side effects are as documented.

    See migration plan §3.1: the SDK live-verified eleven writes against a
    real network (2026-09-20); every other write only logs
    ``warn_uncharacterised_write`` and eeroctl must tell the user to check.
    """

    VERIFIED = "verified"
    """Live-verified against a real network; the documented behaviour is trusted."""

    UNVERIFIED = "unverified"
    """Accepted by the API (2xx), but its side effects are uncharacterised."""

    NO_OP = "no_op"
    """HTTP 200, never applies anything server-side. Never expose these as commands."""


Reboots = Literal["none", "clients", "eero", "mesh"]
"""What a successful write disrupts, independent of :class:`WriteStatus`.

``"none"``: nothing disrupted. ``"clients"``: connected clients drop and
reconnect (e.g. guest network, network rename). ``"eero"``: exactly the
targeted node reboots. ``"mesh"``: every eero on the network reboots,
taking Wi-Fi and internet down network-wide (migration plan §3.1's
mesh-reboot list; DNS carries the same blast radius today).
"""


@dataclass(frozen=True)
class WriteSpec:
    """Everything :func:`require_write_confirmation` needs for one write command.

    Attributes:
        command: The command path exactly as a user types it, e.g.
            ``"network sqm enable"``. Doubles as the registry key.
        risk: The confirmation tier -- LOW/MEDIUM/HIGH.
        status: Whether the SDK has live-verified this write.
        reboots: What a successful write disrupts.
        read_command: The command a user should run to check the result,
            named in the confirmation prompt and in the unverified-write
            note.
        phrase: The typed confirmation phrase for HIGH risk. Required when
            ``risk`` is HIGH; ``require_write_confirmation`` defaults it to
            ``"REBOOT"`` for mesh-reboot writes when omitted.
    """

    command: str
    risk: OperationRisk
    status: WriteStatus
    reboots: Reboots
    read_command: str
    phrase: Optional[str] = None


@dataclass
class SafetyContext:
    """Context for safety checks."""

    force: bool = False
    """Whether --force was specified."""

    non_interactive: bool = False
    """Whether --non-interactive was specified."""

    dry_run: bool = False
    """Whether --dry-run was specified."""


class SafetyError(Exception):
    """Raised when a safety check fails."""

    def __init__(self, message: str, exit_code: int = ExitCode.SAFETY_RAIL):
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


def require_confirmation(
    action: str,
    target: str,
    risk: OperationRisk = OperationRisk.MEDIUM,
    confirmation_phrase: Optional[str] = None,
    ctx: Optional[SafetyContext] = None,
    console: Optional[Console] = None,
) -> bool:
    """Check if operation should proceed based on safety settings.

    Args:
        action: Description of the action (e.g., "reboot")
        target: Target of the action (e.g., "Living Room eero")
        risk: Risk level of the operation
        confirmation_phrase: Required phrase for HIGH risk operations
        ctx: Safety context with force/non_interactive flags
        console: Rich console for prompts

    Returns:
        True if operation should proceed

    Raises:
        SafetyError: If safety check fails and operation should not proceed
    """
    if ctx is None:
        ctx = SafetyContext()

    if console is None:
        console = Console(stderr=True)

    # Dry run always prints and returns False
    if ctx.dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would {action} {target}")
        return False

    # Force bypasses all confirmations
    if ctx.force:
        return True

    # Low risk operations proceed without confirmation
    if risk == OperationRisk.LOW:
        return True

    # Non-interactive mode without force fails
    if ctx.non_interactive:
        raise SafetyError(
            f"Operation '{action}' on '{target}' requires confirmation. "
            "Use --force to proceed in non-interactive mode.",
            exit_code=ExitCode.SAFETY_RAIL,
        )

    # Interactive confirmation
    if risk == OperationRisk.HIGH:
        # High risk requires typed phrase
        if confirmation_phrase is None:
            confirmation_phrase = action.upper().replace(" ", "")

        console.print(
            f"\n[bold yellow]⚠ Warning:[/bold yellow] You are about to {action} {target}."
        )
        console.print(
            "[dim]This is a high-impact operation that may cause service disruption.[/dim]"
        )
        console.print(f"\nTo confirm, type [bold]{confirmation_phrase}[/bold] and press Enter:")

        user_input = Prompt.ask("Confirmation", console=console)

        if user_input != confirmation_phrase:
            raise SafetyError(
                f"Confirmation phrase mismatch. Expected '{confirmation_phrase}'.",
                exit_code=ExitCode.SAFETY_RAIL,
            )
        return True

    else:
        # Medium risk - simple Y/N
        console.print(f"\n[bold]Proceed with {action} on {target}?[/bold]")
        confirmed = Confirm.ask("Continue", default=False, console=console)

        if not confirmed:
            raise SafetyError(
                "Operation cancelled by user.",
                exit_code=ExitCode.SAFETY_RAIL,
            )
        return True


def confirm_or_fail(
    action: str,
    target: str,
    risk: OperationRisk = OperationRisk.MEDIUM,
    confirmation_phrase: Optional[str] = None,
    force: bool = False,
    non_interactive: bool = False,
    dry_run: bool = False,
    console: Optional[Console] = None,
) -> bool:
    """Convenience function combining context creation and confirmation.

    Args:
        action: Description of the action
        target: Target of the action
        risk: Risk level
        confirmation_phrase: Required phrase for HIGH risk
        force: --force flag value
        non_interactive: --non-interactive flag value
        dry_run: --dry-run flag value
        console: Rich console for prompts

    Returns:
        True if operation should proceed

    Raises:
        SafetyError: If safety check fails
    """
    ctx = SafetyContext(force=force, non_interactive=non_interactive, dry_run=dry_run)
    return require_confirmation(
        action=action,
        target=target,
        risk=risk,
        confirmation_phrase=confirmation_phrase,
        ctx=ctx,
        console=console,
    )


# Decorator for commands that require confirmation
def requires_confirmation(
    action: str,
    target_param: str = "target",
    risk: OperationRisk = OperationRisk.MEDIUM,
    confirmation_phrase: Optional[str] = None,
):
    """Decorator to add confirmation requirement to a command.

    Args:
        action: Description of the action
        target_param: Name of the parameter containing the target
        risk: Risk level of the operation
        confirmation_phrase: Required phrase for HIGH risk

    Example:
        @requires_confirmation("reboot", target_param="eero_id", risk=OperationRisk.MEDIUM)
        def reboot(ctx, eero_id: str, force: bool, non_interactive: bool, dry_run: bool):
            ...
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Extract safety-related kwargs
            force = kwargs.get("force", False)
            non_interactive = kwargs.get("non_interactive", False)
            dry_run = kwargs.get("dry_run", False)
            target = kwargs.get(target_param, "unknown")

            try:
                if confirm_or_fail(
                    action=action,
                    target=str(target),
                    risk=risk,
                    confirmation_phrase=confirmation_phrase,
                    force=force,
                    non_interactive=non_interactive,
                    dry_run=dry_run,
                ):
                    return func(*args, **kwargs)
            except SafetyError as e:
                click.echo(f"Error: {e.message}", err=True)
                sys.exit(e.exit_code)

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


MESH_REBOOT_WARNING = (
    "Applying this change reboots every eero on the network. All clients lose "
    "Wi-Fi and internet while the mesh restarts. The outage begins a few minutes "
    "after this command returns, not immediately."
)
"""Warning shown for every mesh-reboot write, unconditionally -- including under
``--force``. Generalised from the DNS-only wording eeroctl 2.x used
(``commands/network/dns.py``'s ``REBOOT_WARNING``); DNS is now one of several
mesh-reboot write families (migration plan §3.1, §3.2 item 2).
"""

UNVERIFIED_WRITE_NOTE = (
    "This write has not been verified against a live network by the SDK; "
    "check the result with `{read_command}`."
)
"""Template for the note appended to every UNVERIFIED write's prompt (migration
plan §3.2 item 2). Printed unconditionally, like the mesh-reboot warning --
a user relying on --force in a script still needs to know to check.
"""

_REBOOT_CONSEQUENCE: Dict[Reboots, str] = {
    "eero": "reboots this eero",
    "clients": "disconnects connected clients",
    "mesh": "reboots every eero on the network",
}
"""Human-readable clause describing what a write disrupts, keyed by
:data:`Reboots`. ``"none"`` intentionally has no entry -- nothing to say."""


def require_write_confirmation(
    spec: WriteSpec,
    target: str,
    ctx: Optional[SafetyContext] = None,
    console: Optional[Console] = None,
) -> bool:
    """Confirm a write, deriving tier, phrasing and warnings from *spec*.

    This is the write-command counterpart to :func:`require_confirmation`:
    instead of every call site hard-coding an :class:`OperationRisk` and a
    confirmation phrase, the tier is looked up once in :data:`WRITE_SPECS`
    and derived here (migration plan §3.2).

    Behaviour:

    - ``spec.reboots == "mesh"``: prints :data:`MESH_REBOOT_WARNING` to
      *console* unconditionally, before any force/non-interactive check, so
      it is visible even when ``--force`` skips the prompt entirely. Tier
      is forced to HIGH with phrase ``spec.phrase or "REBOOT"``.
    - ``spec.status == WriteStatus.UNVERIFIED``: prints the
      :data:`UNVERIFIED_WRITE_NOTE` unconditionally, for the same reason.
    - ``spec.reboots in ("eero", "clients")``: the consequence is folded
      into the action text so it shows up in the MEDIUM/HIGH prompt.
    - Otherwise defers entirely to :func:`require_confirmation` using
      ``spec.risk``.

    Args:
        spec: The write's :class:`WriteSpec`, from :func:`get_write_spec`.
        target: Target of the action (e.g., "Living Room eero"), as passed
            to :func:`require_confirmation` today.
        ctx: Safety context with force/non_interactive/dry_run flags.
        console: Rich console for prompts and warnings.

    Returns:
        True if the caller should proceed with the write.

    Raises:
        SafetyError: If confirmation fails or is required but unavailable.
    """
    if ctx is None:
        ctx = SafetyContext()
    if console is None:
        console = Console(stderr=True)

    if spec.reboots == "mesh":
        console.print(f"[bold yellow]Warning:[/bold yellow] {MESH_REBOOT_WARNING}")

    if spec.status == WriteStatus.UNVERIFIED:
        console.print(f"[dim]{UNVERIFIED_WRITE_NOTE.format(read_command=spec.read_command)}[/dim]")

    risk = spec.risk
    phrase = spec.phrase
    if spec.reboots == "mesh":
        risk = OperationRisk.HIGH
        if phrase is None:
            phrase = "REBOOT"

    action = spec.command
    consequence = _REBOOT_CONSEQUENCE.get(spec.reboots)
    if consequence:
        action = f"{action} ({consequence})"

    return require_confirmation(
        action=action,
        target=target,
        risk=risk,
        confirmation_phrase=phrase,
        ctx=ctx,
        console=console,
    )


def _build_registry(specs: Dict[str, WriteSpec]) -> Dict[str, WriteSpec]:
    """Validate and freeze the write-spec registry.

    Args:
        specs: Mapping of command path to its :class:`WriteSpec`.

    Returns:
        The same mapping, after validation.

    Raises:
        ValueError: If a key does not match its own ``WriteSpec.command``,
            or a ``NO_OP`` write was registered. Per migration plan §3.2
            item 2, a ``NO_OP`` write (e.g. ``set_device_labels``) must
            never be exposed as a command in the first place, so none
            should ever reach this registry; this is a fail-fast guard
            against a future contributor wiring one up by mistake.
    """
    for key, spec in specs.items():
        if spec.command != key:
            raise ValueError(
                f"WriteSpec registry key {key!r} does not match its own command {spec.command!r}"
            )
        if spec.status == WriteStatus.NO_OP:
            raise ValueError(
                f"{key!r} is a NO_OP write and must not be exposed as a command "
                "(migration plan §3.2 item 2)"
            )
        if spec.risk == OperationRisk.HIGH and spec.phrase is None and spec.reboots != "mesh":
            raise ValueError(
                f"{key!r} is HIGH risk but has no confirmation_phrase and is not "
                "a mesh-reboot write (which defaults to REBOOT)"
            )
    return specs


WRITE_SPECS: Dict[str, WriteSpec] = _build_registry(
    {
        # -- network dns: all four write commands share dns.py's own
        # read-first/skip-unchanged logic (_confirm_dns_write), but the
        # confirmation tier itself comes from here now. --
        "network dns mode set": WriteSpec(
            command="network dns mode set",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network dns show",
            phrase="REBOOT",
        ),
        "network dns clear": WriteSpec(
            command="network dns clear",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network dns show",
            phrase="REBOOT",
        ),
        "network dns caching enable": WriteSpec(
            command="network dns caching enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network dns show",
            phrase="REBOOT",
        ),
        "network dns caching disable": WriteSpec(
            command="network dns caching disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network dns show",
            phrase="REBOOT",
        ),
        # -- network sqm: `set_sqm` is not in the SDK's live-verified
        # allowlist and is a documented mesh-reboot write. --
        "network sqm enable": WriteSpec(
            command="network sqm enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network sqm show",
            phrase="REBOOT",
        ),
        "network sqm disable": WriteSpec(
            command="network sqm disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network sqm show",
            phrase="REBOOT",
        ),
        # -- network security: wpa3/band-steering/upnp/ipv6 are mesh-reboot
        # writes (lifted from MEDIUM, Q3 decided); thread stays MEDIUM. --
        "network security wpa3 enable": WriteSpec(
            command="network security wpa3 enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security wpa3 disable": WriteSpec(
            command="network security wpa3 disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security band-steering enable": WriteSpec(
            command="network security band-steering enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security band-steering disable": WriteSpec(
            command="network security band-steering disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security upnp enable": WriteSpec(
            command="network security upnp enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security upnp disable": WriteSpec(
            command="network security upnp disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security ipv6 enable": WriteSpec(
            command="network security ipv6 enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security ipv6 disable": WriteSpec(
            command="network security ipv6 disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        "network security thread enable": WriteSpec(
            command="network security thread enable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network security show",
        ),
        "network security thread disable": WriteSpec(
            command="network security thread disable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network security show",
        ),
        # -- network security mlo: mesh-reboot write (migration plan §4
        # phase C row 34). --
        "network security mlo set": WriteSpec(
            command="network security mlo set",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security show",
            phrase="REBOOT",
        ),
        # -- network security passpoint/proxied-nodes: no reboot, unverified
        # (migration plan §4 phase C row 34); state lives on `get_network`,
        # not `get_security_settings` (§2.7). --
        "network security passpoint enable": WriteSpec(
            command="network security passpoint enable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network security show",
        ),
        "network security passpoint disable": WriteSpec(
            command="network security passpoint disable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network security show",
        ),
        "network security proxied-nodes enable": WriteSpec(
            command="network security proxied-nodes enable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network security show",
        ),
        "network security proxied-nodes disable": WriteSpec(
            command="network security proxied-nodes disable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network security show",
        ),
        # -- network rename: `set_network_name` is not live-verified and
        # disconnects clients while the SSID change propagates. --
        "network rename": WriteSpec(
            command="network rename",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="clients",
            read_command="eero network show",
        ),
        # -- network password/reboot: migration plan §4 phase C row 39. --
        "network password set": WriteSpec(
            command="network password set",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="clients",
            read_command="eero network show",
            phrase="DISCONNECT",
        ),
        "network password clear": WriteSpec(
            command="network password clear",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="clients",
            read_command="eero network show",
            phrase="DISCONNECT",
        ),
        "network reboot": WriteSpec(
            command="network reboot",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network show",
            phrase="REBOOT",
        ),
        # -- network thread set / troubleshoot diagnostics run: migration
        # plan §4 phase C row 40. --
        "network thread set": WriteSpec(
            command="network thread set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network thread show",
        ),
        "troubleshoot diagnostics run": WriteSpec(
            command="troubleshoot diagnostics run",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero troubleshoot doctor",
        ),
        # -- network ddns: no dedicated GET; state read from `get_network`
        # (migration plan §4 phase C row 42, §2.7). --
        "network ddns enable": WriteSpec(
            command="network ddns enable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network show",
        ),
        "network ddns disable": WriteSpec(
            command="network ddns disable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network show",
        ),
        # -- network guest: `set_guest_network`/`set_guest_password` are
        # both in the SDK's live-verified allowlist. --
        "network guest enable": WriteSpec(
            command="network guest enable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="clients",
            read_command="eero network guest show",
        ),
        "network guest disable": WriteSpec(
            command="network guest disable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="clients",
            read_command="eero network guest show",
        ),
        "network guest set": WriteSpec(
            command="network guest set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="clients",
            read_command="eero network guest show",
        ),
        "network guest password set": WriteSpec(
            command="network guest password set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="clients",
            read_command="eero network guest show",
        ),
        "network guest password clear": WriteSpec(
            command="network guest password clear",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="clients",
            read_command="eero network guest show",
        ),
        # -- network backup: `set_backup_internet` replaced the removed
        # `set_backup_network` and is not in the live-verified allowlist. --
        "network backup enable": WriteSpec(
            command="network backup enable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network backup show",
        ),
        "network backup disable": WriteSpec(
            command="network backup disable",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network backup show",
        ),
        # -- device: `set_device_type` is in the SDK's live-verified
        # allowlist (migration plan §3.1, §4 phase B row 25). --
        "device type set": WriteSpec(
            command="device type set",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero device show <id>",
        ),
        # -- device: `block_device` is form-encoded and unverified;
        # `unblock_device`/`pause_device` are both live-verified. --
        "device block": WriteSpec(
            command="device block",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero device list",
        ),
        "device unblock": WriteSpec(
            command="device unblock",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero device list",
        ),
        "device pause": WriteSpec(
            command="device pause",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero device list",
        ),
        "device unpause": WriteSpec(
            command="device unpause",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero device list",
        ),
        # -- profile: none of rename/delete/pause/schedule are in the
        # SDK's live-verified allowlist (only `pause_device` is verified,
        # not `pause_profile`). Risk levels are unchanged from 2.x. --
        "profile rename": WriteSpec(
            command="profile rename",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile list",
        ),
        "profile delete": WriteSpec(
            command="profile delete",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile list",
            phrase="DELETE",
        ),
        "profile pause": WriteSpec(
            command="profile pause",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile list",
        ),
        "profile unpause": WriteSpec(
            command="profile unpause",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile list",
        ),
        "profile devices set": WriteSpec(
            command="profile devices set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile show <profile>",
        ),
        # -- profile dns: per-profile domain allow/block (Eero Plus),
        # migration plan §4 phase C row 41. --
        "profile dns allow": WriteSpec(
            command="profile dns allow",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile show <profile>",
        ),
        "profile dns block": WriteSpec(
            command="profile dns block",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile show <profile>",
        ),
        "profile schedule set": WriteSpec(
            command="profile schedule set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile schedule show",
        ),
        "profile schedule clear": WriteSpec(
            command="profile schedule clear",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile schedule show",
        ),
        "profile schedule delete": WriteSpec(
            command="profile schedule delete",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile schedule show <profile>",
        ),
        # -- eero: `reboot_eero` is live-verified; it is the "eero" reboot
        # class by definition, not "mesh" -- only the targeted node moves. --
        "eero reboot": WriteSpec(
            command="eero reboot",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.VERIFIED,
            reboots="eero",
            read_command="eero eero list",
        ),
        # -- eero led: `set_led`/`set_led_brightness` are both live-verified
        # (and, unlike v7, actually take effect). --
        "eero led on": WriteSpec(
            command="eero led on",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero eero led show",
        ),
        "eero led off": WriteSpec(
            command="eero led off",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero eero led show",
        ),
        "eero led brightness": WriteSpec(
            command="eero led brightness",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero eero led show",
        ),
        "eero led cycle": WriteSpec(
            command="eero led cycle",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero led show",
        ),
        # -- eero: location/pppoe/ports/port -- migration plan §4 phase C
        # row 36. --
        "eero location set": WriteSpec(
            command="eero location set",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero show <id>",
        ),
        "eero pppoe set": WriteSpec(
            command="eero pppoe set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero show <id>",
        ),
        "eero ports cycle": WriteSpec(
            command="eero ports cycle",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero list",
        ),
        "eero ports cycle --reboot": WriteSpec(
            command="eero ports cycle --reboot",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="eero",
            read_command="eero eero list",
        ),
        "eero port": WriteSpec(
            command="eero port",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero show <id>",
        ),
        # -- eero nightlight: none of the nightlight writes are in the
        # live-verified allowlist, and no Beacon was available to confirm
        # them by hand either (migration plan Q4). --
        "eero nightlight on": WriteSpec(
            command="eero nightlight on",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero nightlight show",
        ),
        "eero nightlight off": WriteSpec(
            command="eero nightlight off",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero nightlight show",
        ),
        "eero nightlight brightness": WriteSpec(
            command="eero nightlight brightness",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero nightlight show",
        ),
        "eero nightlight schedule": WriteSpec(
            command="eero nightlight schedule",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero nightlight show",
        ),
        "eero nightlight override": WriteSpec(
            command="eero nightlight override",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero eero nightlight show",
        ),
        # -- eero updates apply: reboots every node on the network
        # (migration plan §4 phase C row 38). --
        "eero updates apply": WriteSpec(
            command="eero updates apply",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero eero updates show",
            phrase="REBOOT",
        ),
        # -- network support bundle export: not an SDK write at all -- it is
        # two reads (`get_support`, `get_diagnostics`) written to a local
        # file. Confirmed because the bundle can be large and may contain
        # sensitive diagnostics, not because a server-side write is
        # uncharacterised. UNVERIFIED is the closest fit of the three
        # statuses (VERIFIED would wrongly imply a live-verified write
        # happened; NO_OP means something else entirely -- §3.2 item 2). --
        "network support bundle export": WriteSpec(
            command="network support bundle export",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network support show",
        ),
        # -- profile apps block/unblock: `set_profile_blocked_applications`
        # REPLACES the profile's entire blocked-application list in one
        # call and is not in the SDK's live-verified allowlist -- the
        # widest-blast-radius write eeroctl exposes (security review,
        # commit 7 follow-up). --
        "profile apps block": WriteSpec(
            command="profile apps block",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile apps list",
        ),
        "profile apps unblock": WriteSpec(
            command="profile apps unblock",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile apps list",
        ),
        # -- device rename: `set_device_nickname` is in the SDK's
        # live-verified allowlist (DIGEST §5; migration plan §3.1). --
        "device rename": WriteSpec(
            command="device rename",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero device list",
        ),
        # -- profile create: `create_profile` is not in the live-verified
        # allowlist. --
        "profile create": WriteSpec(
            command="profile create",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero profile list",
        ),
        # -- network speedtest run: `run_speed_test` is in the SDK's
        # live-verified allowlist (202, data: null -- no result to check
        # here, but the write itself is trusted). Registered alongside the
        # security-review fold-in so the completeness test below has full
        # coverage; behaviour is unchanged (LOW = no prompt either way). --
        "network speedtest run": WriteSpec(
            command="network speedtest run",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero network speedtest show",
        ),
        # -- network forwards: create/update/delete are all unverified
        # (migration plan §4 phase C row 32). --
        "network forwards create": WriteSpec(
            command="network forwards create",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network forwards list",
        ),
        "network forwards update": WriteSpec(
            command="network forwards update",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network forwards list",
        ),
        "network forwards delete": WriteSpec(
            command="network forwards delete",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network forwards list",
        ),
        # -- network dhcp reservation: create/update/delete are all
        # unverified (migration plan §4 phase C row 33). --
        "network dhcp reservation create": WriteSpec(
            command="network dhcp reservation create",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network dhcp reservations",
        ),
        "network dhcp reservation update": WriteSpec(
            command="network dhcp reservation update",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network dhcp reservations",
        ),
        "network dhcp reservation delete": WriteSpec(
            command="network dhcp reservation delete",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network dhcp reservations",
        ),
        # -- network dhcp set/connection-mode/nat-randomization: all
        # mesh-reboot writes (migration plan §4 phase C row 35). --
        "network dhcp set": WriteSpec(
            command="network dhcp set",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network show",
            phrase="REBOOT",
        ),
        "network dhcp connection-mode set": WriteSpec(
            command="network dhcp connection-mode set",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network show",
            phrase="REBOOT",
        ),
        "network dhcp nat-randomization enable": WriteSpec(
            command="network dhcp nat-randomization enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network show",
            phrase="REBOOT",
        ),
        "network dhcp nat-randomization disable": WriteSpec(
            command="network dhcp nat-randomization disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network show",
            phrase="REBOOT",
        ),
        # -- network wpa3 set / network security fast-transition: both
        # mesh-reboot writes (migration plan §4 phase C row 30). --
        "network wpa3 set": WriteSpec(
            command="network wpa3 set",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network wpa3 show",
            phrase="REBOOT",
        ),
        "network security fast-transition enable": WriteSpec(
            command="network security fast-transition enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security fast-transition show",
            phrase="REBOOT",
        ),
        "network security fast-transition disable": WriteSpec(
            command="network security fast-transition disable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network security fast-transition show",
            phrase="REBOOT",
        ),
        # -- network dns policy: network-wide content-filtering allow/block
        # (Eero Plus); no mesh reboot (migration plan §4 phase C row 41). --
        "network dns policy allow": WriteSpec(
            command="network dns policy allow",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network dns policy show",
        ),
        "network dns policy block": WriteSpec(
            command="network dns policy block",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network dns policy show",
        ),
        "network dns policy allow-cnames": WriteSpec(
            command="network dns policy allow-cnames",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network dns policy show",
        ),
        # -- account: name/email/phone/consents/push -- all account-scoped,
        # unverified writes (migration plan §4 phase C, `account name set`
        # row). Two-step email/phone flows print the follow-up command
        # themselves rather than via read_command. --
        "account name set": WriteSpec(
            command="account name set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero auth status",
        ),
        "account email set": WriteSpec(
            command="account email set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero auth status",
        ),
        "account email verify": WriteSpec(
            command="account email verify",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero auth status",
        ),
        "account phone set": WriteSpec(
            command="account phone set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero auth status",
        ),
        "account phone verify": WriteSpec(
            command="account phone verify",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero auth status",
        ),
        "account consents": WriteSpec(
            command="account consents",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero auth status",
        ),
        "account push set": WriteSpec(
            command="account push set",
            risk=OperationRisk.MEDIUM,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero account push set",
        ),
        # -- network notifications: set/mark-read -- both LOW + unverified
        # (migration plan §4 phase C, `network notifications set` row). --
        "network notifications set": WriteSpec(
            command="network notifications set",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network notifications show",
        ),
        "network notifications mark-read": WriteSpec(
            command="network notifications mark-read",
            risk=OperationRisk.LOW,
            status=WriteStatus.UNVERIFIED,
            reboots="none",
            read_command="eero network notifications show",
        ),
    }
)
"""The write-command registry, replacing the old ``OPERATION_RISKS`` mapping.

One entry per command that calls :func:`require_write_confirmation` today.
Phase B/C commands from the migration plan (§4) are added by later commits
as they are implemented -- this registry only covers what the CLI already
exposes.
"""


def get_write_spec(command: str) -> WriteSpec:
    """Look up a write command's :class:`WriteSpec`.

    Args:
        command: The command path, e.g. ``"network sqm enable"``.

    Returns:
        The registered :class:`WriteSpec`.

    Raises:
        KeyError: If *command* has no registered spec. This is a
            programming error (a call site that was not registered), not a
            user-facing failure, so it is left to propagate rather than
            translated into a ``SafetyError``.
    """
    try:
        return WRITE_SPECS[command]
    except KeyError:
        raise KeyError(f"No WriteSpec registered for command {command!r}") from None
