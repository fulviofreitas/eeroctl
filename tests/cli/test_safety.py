"""Unit tests for eero.cli.safety module.

Tests cover:
- SafetyContext dataclass
- SafetyError exception
- OperationRisk enum
- require_confirmation function
- confirm_or_fail convenience function
- requires_confirmation decorator
- WriteStatus enum and WriteSpec dataclass
- WRITE_SPECS registry and get_write_spec
- require_write_confirmation function
"""

from unittest.mock import MagicMock, patch

import click
import pytest

from eeroctl.exit_codes import ExitCode
from eeroctl.safety import (
    MESH_REBOOT_WARNING,
    WRITE_SPECS,
    OperationRisk,
    SafetyContext,
    SafetyError,
    WriteSpec,
    WriteStatus,
    confirm_or_fail,
    get_write_spec,
    require_confirmation,
    require_write_confirmation,
    requires_confirmation,
)

# ========================== OperationRisk Tests ==========================


class TestOperationRisk:
    """Tests for OperationRisk enum."""

    def test_low_risk_value(self):
        """Test LOW risk has correct value."""
        assert OperationRisk.LOW == "low"

    def test_medium_risk_value(self):
        """Test MEDIUM risk has correct value."""
        assert OperationRisk.MEDIUM == "medium"

    def test_high_risk_value(self):
        """Test HIGH risk has correct value."""
        assert OperationRisk.HIGH == "high"

    def test_risks_are_strings(self):
        """Test all risks are string enums."""
        for risk in OperationRisk:
            assert isinstance(risk.value, str)


# ========================== SafetyContext Tests ==========================


class TestSafetyContext:
    """Tests for SafetyContext dataclass."""

    def test_default_values(self):
        """Test SafetyContext has correct defaults."""
        ctx = SafetyContext()

        assert ctx.force is False
        assert ctx.non_interactive is False
        assert ctx.dry_run is False

    def test_custom_values(self):
        """Test SafetyContext accepts custom values."""
        ctx = SafetyContext(
            force=True,
            non_interactive=True,
            dry_run=True,
        )

        assert ctx.force is True
        assert ctx.non_interactive is True
        assert ctx.dry_run is True


# ========================== SafetyError Tests ==========================


class TestSafetyError:
    """Tests for SafetyError exception."""

    def test_message_and_exit_code(self):
        """Test SafetyError stores message and exit code."""
        error = SafetyError("Operation cancelled", ExitCode.SAFETY_RAIL)

        assert error.message == "Operation cancelled"
        assert error.exit_code == ExitCode.SAFETY_RAIL

    def test_default_exit_code(self):
        """Test SafetyError uses SAFETY_RAIL as default exit code."""
        error = SafetyError("Cancelled")

        assert error.exit_code == ExitCode.SAFETY_RAIL

    def test_is_exception(self):
        """Test SafetyError is an Exception."""
        error = SafetyError("Test")

        assert isinstance(error, Exception)

        with pytest.raises(SafetyError):
            raise error


# ========================== require_confirmation Tests ==========================


class TestRequireConfirmation:
    """Tests for require_confirmation function."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create a mock console."""
        console = MagicMock()
        console.print = MagicMock()
        return console

    def test_dry_run_returns_false(self, mock_console):
        """Test dry run always returns False and prints message."""
        ctx = SafetyContext(dry_run=True)

        result = require_confirmation(
            action="reboot",
            target="Living Room",
            risk=OperationRisk.MEDIUM,
            ctx=ctx,
            console=mock_console,
        )

        assert result is False
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "DRY RUN" in call_args

    def test_force_bypasses_confirmation(self, mock_console):
        """Test force flag bypasses all confirmations."""
        ctx = SafetyContext(force=True)

        result = require_confirmation(
            action="factory reset",
            target="network",
            risk=OperationRisk.HIGH,
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        # Should not print anything
        mock_console.print.assert_not_called()

    def test_low_risk_no_confirmation_needed(self, mock_console):
        """Test LOW risk operations proceed without confirmation."""
        ctx = SafetyContext()

        result = require_confirmation(
            action="rename",
            target="device",
            risk=OperationRisk.LOW,
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        mock_console.print.assert_not_called()

    def test_non_interactive_without_force_raises(self, mock_console):
        """Test non-interactive mode without force raises SafetyError."""
        ctx = SafetyContext(non_interactive=True, force=False)

        with pytest.raises(SafetyError) as exc_info:
            require_confirmation(
                action="reboot",
                target="eero",
                risk=OperationRisk.MEDIUM,
                ctx=ctx,
                console=mock_console,
            )

        assert exc_info.value.exit_code == ExitCode.SAFETY_RAIL
        assert "--force" in exc_info.value.message

    @patch("eeroctl.safety.Confirm.ask")
    def test_medium_risk_prompts_user(self, mock_confirm, mock_console):
        """Test MEDIUM risk prompts for Y/N confirmation."""
        mock_confirm.return_value = True
        ctx = SafetyContext()

        result = require_confirmation(
            action="reboot",
            target="Living Room eero",
            risk=OperationRisk.MEDIUM,
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        mock_confirm.assert_called_once()

    @patch("eeroctl.safety.Confirm.ask")
    def test_medium_risk_user_declines(self, mock_confirm, mock_console):
        """Test MEDIUM risk raises when user declines."""
        mock_confirm.return_value = False
        ctx = SafetyContext()

        with pytest.raises(SafetyError) as exc_info:
            require_confirmation(
                action="reboot",
                target="eero",
                risk=OperationRisk.MEDIUM,
                ctx=ctx,
                console=mock_console,
            )

        assert "cancelled" in exc_info.value.message.lower()

    @patch("eeroctl.safety.Prompt.ask")
    def test_high_risk_requires_typed_confirmation(self, mock_prompt, mock_console):
        """Test HIGH risk requires typed confirmation phrase."""
        mock_prompt.return_value = "FACTORYRESET"
        ctx = SafetyContext()

        result = require_confirmation(
            action="factory reset",
            target="network",
            risk=OperationRisk.HIGH,
            confirmation_phrase="FACTORYRESET",
            ctx=ctx,
            console=mock_console,
        )

        assert result is True
        mock_prompt.assert_called_once()

    @patch("eeroctl.safety.Prompt.ask")
    def test_high_risk_wrong_phrase_raises(self, mock_prompt, mock_console):
        """Test HIGH risk raises when phrase doesn't match."""
        mock_prompt.return_value = "wrong"
        ctx = SafetyContext()

        with pytest.raises(SafetyError) as exc_info:
            require_confirmation(
                action="factory reset",
                target="network",
                risk=OperationRisk.HIGH,
                confirmation_phrase="FACTORYRESET",
                ctx=ctx,
                console=mock_console,
            )

        assert "mismatch" in exc_info.value.message.lower()

    @patch("eeroctl.safety.Prompt.ask")
    def test_high_risk_auto_generates_phrase(self, mock_prompt, mock_console):
        """Test HIGH risk auto-generates confirmation phrase if not provided."""
        # Action is "factory reset" -> phrase becomes "FACTORYRESET"
        mock_prompt.return_value = "FACTORYRESET"
        ctx = SafetyContext()

        result = require_confirmation(
            action="factory reset",
            target="network",
            risk=OperationRisk.HIGH,
            # No confirmation_phrase provided
            ctx=ctx,
            console=mock_console,
        )

        assert result is True

    def test_default_context_creation(self):
        """Test function creates default context if none provided."""
        # This should not raise - it creates a default SafetyContext
        result = require_confirmation(
            action="rename",
            target="device",
            risk=OperationRisk.LOW,
        )

        assert result is True


# ========================== confirm_or_fail Tests ==========================


class TestConfirmOrFail:
    """Tests for confirm_or_fail convenience function."""

    def test_force_returns_true(self):
        """Test force=True returns True immediately."""
        result = confirm_or_fail(
            action="reboot",
            target="eero",
            risk=OperationRisk.MEDIUM,
            force=True,
        )

        assert result is True

    def test_dry_run_returns_false(self):
        """Test dry_run=True returns False."""
        result = confirm_or_fail(
            action="reboot",
            target="eero",
            risk=OperationRisk.MEDIUM,
            dry_run=True,
        )

        assert result is False

    def test_non_interactive_raises_without_force(self):
        """Test non_interactive without force raises SafetyError."""
        with pytest.raises(SafetyError):
            confirm_or_fail(
                action="reboot",
                target="eero",
                risk=OperationRisk.MEDIUM,
                non_interactive=True,
                force=False,
            )

    def test_low_risk_always_passes(self):
        """Test LOW risk always returns True."""
        result = confirm_or_fail(
            action="view",
            target="settings",
            risk=OperationRisk.LOW,
        )

        assert result is True


# ========================== requires_confirmation Decorator Tests ==========================


class TestRequiresConfirmationDecorator:
    """Tests for requires_confirmation decorator."""

    def test_decorator_passes_with_force(self):
        """Test decorated function executes when force=True."""
        executed = []

        @requires_confirmation("test action", risk=OperationRisk.MEDIUM)
        def test_func(target, force=False):
            executed.append(target)
            return "success"

        result = test_func(target="test", force=True)

        assert result == "success"
        assert executed == ["test"]

    def test_decorator_with_low_risk(self):
        """Test decorated function executes for LOW risk."""
        executed = []

        @requires_confirmation("view", risk=OperationRisk.LOW)
        def view_func(target):
            executed.append(target)
            return "viewed"

        result = view_func(target="item")

        assert result == "viewed"
        assert executed == ["item"]

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function name."""

        @requires_confirmation("test", risk=OperationRisk.LOW)
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_decorator_preserves_docstring(self):
        """Test decorator preserves docstring."""

        @requires_confirmation("test", risk=OperationRisk.LOW)
        def documented_function():
            """This is documentation."""
            pass

        assert documented_function.__doc__ == """This is documentation."""


# ========================== WriteStatus / WriteSpec Tests ==========================


class TestWriteStatus:
    """Tests for WriteStatus enum."""

    def test_verified_value(self):
        assert WriteStatus.VERIFIED == "verified"

    def test_unverified_value(self):
        assert WriteStatus.UNVERIFIED == "unverified"

    def test_no_op_value(self):
        assert WriteStatus.NO_OP == "no_op"


class TestWriteSpecDataclass:
    """Tests for the WriteSpec dataclass shape."""

    def test_minimal_construction(self):
        spec = WriteSpec(
            command="eero led on",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero eero led show",
        )
        assert spec.phrase is None

    def test_is_frozen(self):
        spec = WriteSpec(
            command="eero led on",
            risk=OperationRisk.LOW,
            status=WriteStatus.VERIFIED,
            reboots="none",
            read_command="eero eero led show",
        )
        with pytest.raises(AttributeError):
            spec.risk = OperationRisk.HIGH  # type: ignore[misc]


# ========================== WRITE_SPECS Registry Tests ==========================


class TestWriteSpecsRegistry:
    """Tests for the WRITE_SPECS registry, replacing the old OPERATION_RISKS map."""

    # Every command path that calls require_write_confirmation today (grepped
    # from the command modules). Kept as an explicit list, rather than
    # introspecting the Click command tree, because several of these are
    # still dispatched through shared helper functions (`_set_sqm_enabled`,
    # `_set_security_setting`, ...) rather than one function per command.
    EXPECTED_COMMANDS = [
        "network dns mode set",
        "network dns clear",
        "network dns caching enable",
        "network dns caching disable",
        "network sqm enable",
        "network sqm disable",
        "network security wpa3 enable",
        "network security wpa3 disable",
        "network security band-steering enable",
        "network security band-steering disable",
        "network security upnp enable",
        "network security upnp disable",
        "network security ipv6 enable",
        "network security ipv6 disable",
        "network security thread enable",
        "network security thread disable",
        "network security mlo set",
        "network security passpoint enable",
        "network security passpoint disable",
        "network security proxied-nodes enable",
        "network security proxied-nodes disable",
        "network rename",
        "network guest enable",
        "network guest disable",
        "network guest set",
        "network guest password set",
        "network guest password clear",
        "network backup enable",
        "network backup disable",
        "device type set",
        "device block",
        "device unblock",
        "device pause",
        "device unpause",
        "profile rename",
        "profile delete",
        "profile pause",
        "profile unpause",
        "profile schedule set",
        "profile schedule clear",
        "profile schedule delete",
        "profile devices set",
        "eero reboot",
        "eero led on",
        "eero led off",
        "eero led brightness",
        "eero nightlight on",
        "eero nightlight off",
        "eero nightlight brightness",
        "eero nightlight schedule",
        "network support bundle export",
        "profile apps block",
        "profile apps unblock",
        "device rename",
        "profile create",
        "network speedtest run",
        "network forwards create",
        "network forwards update",
        "network forwards delete",
        "network dhcp reservation create",
        "network dhcp reservation update",
        "network dhcp reservation delete",
        "network dhcp set",
        "network dhcp connection-mode set",
        "network dhcp nat-randomization enable",
        "network dhcp nat-randomization disable",
    ]

    def test_every_expected_command_is_registered(self):
        """Every write command path this commit wires up has a WriteSpec."""
        for command in self.EXPECTED_COMMANDS:
            assert command in WRITE_SPECS, f"{command!r} missing from WRITE_SPECS"

    def test_no_unexpected_commands(self):
        """The registry has exactly the commands this commit wires up.

        A new entry here means a command call site started consuming the
        registry without updating this list -- update EXPECTED_COMMANDS
        alongside the new command.
        """
        assert set(WRITE_SPECS) == set(self.EXPECTED_COMMANDS)

    def test_registry_key_matches_spec_command(self):
        """Every registry key equals its own WriteSpec.command."""
        for key, spec in WRITE_SPECS.items():
            assert key == spec.command

    def test_no_command_module_bypasses_the_registry(self):
        """Every confirmation in src/eeroctl/commands goes through get_write_spec.

        Enforces the invariant that
        ``grep -rn "confirm_or_fail\\|require_confirmation(" src/eeroctl/commands``
        returns nothing: no command module may call the old, unregistered
        ``confirm_or_fail``/``require_confirmation`` helpers directly. Walking
        the actual source tree (rather than trusting EXPECTED_COMMANDS) means
        a future command that reverts to the old helpers fails this test
        even if its command path is never added to EXPECTED_COMMANDS.
        """
        import re
        from pathlib import Path

        import eeroctl.commands as commands_pkg

        commands_dir = Path(commands_pkg.__file__).parent
        pattern = re.compile(r"confirm_or_fail\(|require_confirmation\(")
        offenders = []

        for path in commands_dir.rglob("*.py"):
            text = path.read_text()
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(commands_dir)}:{lineno}: {line.strip()}")

        message = "Found direct confirm_or_fail/require_confirmation calls:\n" + "\n".join(
            offenders
        )
        assert not offenders, message

    # Client methods every write-verb `await client.<name>(` call site in
    # src/eeroctl/commands actually uses today, mapped to the WRITE_SPECS
    # command path(s) that cover it. This is the ground truth
    # `test_every_write_call_site_has_a_registered_command` below checks
    # new/changed call sites against: a write call using a method name not
    # in this table, or a command path this table names that is missing
    # from WRITE_SPECS, fails loudly instead of shipping an unconfirmed,
    # unregistered write (as `profile apps block`/`unblock` did before this
    # security-review fold-in -- `set_profile_blocked_applications` REPLACES
    # a profile's entire blocked-application list and had neither a prompt
    # nor a WriteSpec).
    _CLIENT_METHOD_TO_COMMANDS = {
        "reboot_eero": ["eero reboot"],
        "set_led": ["eero led on", "eero led off"],
        "set_led_brightness": ["eero led brightness"],
        "set_nightlight": ["eero nightlight on", "eero nightlight off"],
        "set_nightlight_brightness": ["eero nightlight brightness"],
        "set_nightlight_schedule": ["eero nightlight schedule"],
        "run_speed_test": ["network speedtest run"],
        "set_backup_internet": ["network backup enable", "network backup disable"],
        "set_network_name": ["network rename"],
        "clear_custom_dns": ["network dns mode set", "network dns clear"],
        "set_dns_mode": ["network dns mode set"],
        "set_custom_dns_ipv4": ["network dns mode set"],
        "set_custom_dns_ipv6": ["network dns mode set"],
        "set_custom_dns": ["network dns mode set"],
        "set_dns_caching": ["network dns caching enable", "network dns caching disable"],
        "set_guest_network": ["network guest enable", "network guest disable", "network guest set"],
        "set_guest_password": ["network guest set", "network guest password set"],
        "clear_guest_password": ["network guest password clear"],
        "set_sqm": ["network sqm enable", "network sqm disable"],
        "set_device_nickname": ["device rename"],
        "set_device_type": ["device type set"],
        "block_device": ["device block"],
        "unblock_device": ["device unblock"],
        "pause_device": ["device pause", "device unpause"],
        "create_profile": ["profile create"],
        "rename_profile": ["profile rename"],
        "delete_profile": ["profile delete"],
        "pause_profile": ["profile pause", "profile unpause"],
        "set_profile_blocked_applications": ["profile apps block", "profile apps unblock"],
        "enable_bedtime": ["profile schedule set"],
        "clear_profile_schedule": ["profile schedule clear"],
        "delete_schedule": ["profile schedule delete"],
        "set_profile_devices": ["profile devices set"],
        "create_forward": ["network forwards create"],
        "update_forward": ["network forwards update"],
        "delete_forward": ["network forwards delete"],
        "create_reservation": ["network dhcp reservation create"],
        "update_reservation": ["network dhcp reservation update"],
        "delete_reservation": ["network dhcp reservation delete"],
        "set_mlo_mode": ["network security mlo set"],
        "set_dhcp": ["network dhcp set"],
        "set_connection_mode": ["network dhcp connection-mode set"],
        "set_nat_port_randomization": [
            "network dhcp nat-randomization enable",
            "network dhcp nat-randomization disable",
        ],
    }

    def test_every_write_call_site_has_a_registered_command(self):
        """Static-analysis regression test for the security-review fold-in.

        Walks every command module for ``await client.<write-verb>(`` --
        the same verb-prefix vocabulary the SDK's own
        ``_WRITE_PREFIXES`` uses to spot writes it hasn't warned about
        (DIGEST §5) -- and asserts the called method is a *known, tracked*
        write with a registered command in :data:`WRITE_SPECS`. A future
        write call using an untracked method name fails here instead of
        shipping with no confirmation and no spec.
        """
        import re
        from pathlib import Path

        import eeroctl.commands as commands_pkg

        write_verb_pattern = re.compile(
            r"await client\."
            r"(set_|create_|delete_|update_|block_|unblock_|pause_|unpause_|reboot_|"
            r"enable_|disable_|clear_|allow_|add_|remove_|apply_|run_speed|rename_|"
            r"configure_|mark_|regenerate_|node_action|port_action|led_cycle|"
            r"nightlight_override|request_)"
        )
        method_pattern = re.compile(r"await client\.(\w+)\(")

        commands_dir = Path(commands_pkg.__file__).parent
        offenders = []
        seen_methods = set()

        for path in commands_dir.rglob("*.py"):
            text = path.read_text()
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not write_verb_pattern.search(line):
                    continue
                match = method_pattern.search(line)
                method = match.group(1) if match else None
                if method is None or method not in self._CLIENT_METHOD_TO_COMMANDS:
                    offenders.append(
                        f"{path.relative_to(commands_dir)}:{lineno}: "
                        f"untracked write method {method!r} -- add it to "
                        "_CLIENT_METHOD_TO_COMMANDS and register a WriteSpec"
                    )
                else:
                    seen_methods.add(method)

        for method, commands in self._CLIENT_METHOD_TO_COMMANDS.items():
            for command in commands:
                if command not in WRITE_SPECS:
                    offenders.append(
                        f"_CLIENT_METHOD_TO_COMMANDS[{method!r}] names {command!r}, "
                        "which is missing from WRITE_SPECS"
                    )

        message = "Write-call coverage gaps:\n" + "\n".join(offenders)
        assert not offenders, message
        # Sanity: the table isn't stale -- every entry was actually observed
        # in the source this run (catches a method that was removed from
        # every command but left in the table).
        assert seen_methods == set(self._CLIENT_METHOD_TO_COMMANDS), (
            "_CLIENT_METHOD_TO_COMMANDS has entries no longer used in "
            f"src/eeroctl/commands: {set(self._CLIENT_METHOD_TO_COMMANDS) - seen_methods}"
        )

    def test_no_no_op_specs_registered(self):
        """NO_OP writes (e.g. set_device_labels) must never be exposed."""
        for spec in WRITE_SPECS.values():
            assert spec.status != WriteStatus.NO_OP

    @pytest.mark.parametrize(
        "command",
        [
            "network dns mode set",
            "network dns clear",
            "network dns caching enable",
            "network dns caching disable",
            "network sqm enable",
            "network sqm disable",
            "network security wpa3 enable",
            "network security wpa3 disable",
            "network security band-steering enable",
            "network security band-steering disable",
            "network security upnp enable",
            "network security upnp disable",
            "network security ipv6 enable",
            "network security ipv6 disable",
        ],
    )
    def test_mesh_reboot_specs_are_high_with_reboot_phrase(self, command):
        """Every mesh-reboot write is HIGH risk with the REBOOT phrase (Q3, decided)."""
        spec = get_write_spec(command)
        assert spec.reboots == "mesh"
        assert spec.risk == OperationRisk.HIGH
        assert spec.phrase == "REBOOT"

    def test_thread_toggle_was_not_lifted_to_high(self):
        """Only wpa3/band-steering/upnp/ipv6 were lifted; thread stays MEDIUM."""
        for command in ("network security thread enable", "network security thread disable"):
            spec = get_write_spec(command)
            assert spec.risk == OperationRisk.MEDIUM
            assert spec.reboots == "none"

    def test_eero_reboot_is_eero_scoped_not_mesh(self):
        """reboot_eero only reboots the targeted node, not the whole mesh."""
        spec = get_write_spec("eero reboot")
        assert spec.reboots == "eero"
        assert spec.status == WriteStatus.VERIFIED

    def test_verified_writes_match_sdk_allowlist(self):
        """Only SDK-live-verified writes are marked VERIFIED (migration plan §3.1)."""
        verified = {cmd for cmd, spec in WRITE_SPECS.items() if spec.status == WriteStatus.VERIFIED}
        assert verified == {
            "network guest enable",
            "network guest disable",
            "network guest set",
            "network guest password set",
            "network guest password clear",
            "device type set",
            "device unblock",
            "device pause",
            "device unpause",
            "device rename",
            "eero reboot",
            "eero led on",
            "eero led off",
            "eero led brightness",
            "network speedtest run",
        }

    def test_get_write_spec_unknown_command_raises(self):
        """An unregistered command path raises KeyError, not a silent default."""
        with pytest.raises(KeyError):
            get_write_spec("network warp-drive enable")


# ========================== require_write_confirmation Tests ==========================


class TestRequireWriteConfirmation:
    """Tests for require_write_confirmation."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        console = MagicMock()
        console.print = MagicMock()
        return console

    def test_mesh_reboot_warning_printed_before_force_check(self, mock_console):
        """The mesh-reboot warning prints even under --force (dns.py's contract, generalised)."""
        ctx = SafetyContext(force=True)
        spec = get_write_spec("network sqm enable")

        result = require_write_confirmation(spec, "network", ctx=ctx, console=mock_console)

        assert result is True
        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "reboots every eero" in printed

    def test_mesh_reboot_warning_text_matches_constant(self, mock_console):
        ctx = SafetyContext(force=True)
        spec = get_write_spec("network sqm enable")

        require_write_confirmation(spec, "network", ctx=ctx, console=mock_console)

        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert MESH_REBOOT_WARNING in printed

    def test_non_mesh_write_prints_no_reboot_warning(self, mock_console):
        """A non-mesh write (device unblock) must not print the mesh warning."""
        ctx = SafetyContext(force=True)
        spec = get_write_spec("device unblock")

        require_write_confirmation(spec, "MyPhone", ctx=ctx, console=mock_console)

        for call in mock_console.print.call_args_list:
            assert "reboots every eero" not in str(call.args[0])

    def test_unverified_specs_print_the_note_line(self, mock_console):
        """UNVERIFIED writes get the 'has not been verified' note, unconditionally."""
        ctx = SafetyContext(force=True)
        spec = get_write_spec("device block")
        assert spec.status == WriteStatus.UNVERIFIED

        require_write_confirmation(spec, "MyPhone", ctx=ctx, console=mock_console)

        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "has not been verified against a live network" in printed
        assert spec.read_command in printed

    def test_verified_specs_do_not_print_the_note_line(self, mock_console):
        """VERIFIED writes never get the unverified note."""
        ctx = SafetyContext(force=True)
        spec = get_write_spec("device unblock")
        assert spec.status == WriteStatus.VERIFIED

        require_write_confirmation(spec, "MyPhone", ctx=ctx, console=mock_console)

        printed = " ".join(str(c.args[0]) for c in mock_console.print.call_args_list)
        assert "has not been verified" not in printed

    def test_low_risk_returns_true_without_prompting(self, mock_console):
        ctx = SafetyContext()
        spec = get_write_spec("eero led on")

        result = require_write_confirmation(spec, "Living Room", ctx=ctx, console=mock_console)

        assert result is True

    @patch("eeroctl.safety.Prompt.ask")
    def test_high_risk_prompts_for_the_registered_phrase(self, mock_prompt, mock_console):
        mock_prompt.return_value = "REBOOT"
        ctx = SafetyContext()
        spec = get_write_spec("network sqm enable")

        result = require_write_confirmation(spec, "network", ctx=ctx, console=mock_console)

        assert result is True
        mock_prompt.assert_called_once()

    @patch("eeroctl.safety.Confirm.ask")
    def test_medium_risk_prompts_yes_no(self, mock_confirm, mock_console):
        mock_confirm.return_value = True
        ctx = SafetyContext()
        spec = get_write_spec("eero reboot")

        result = require_write_confirmation(spec, "Living Room", ctx=ctx, console=mock_console)

        assert result is True
        mock_confirm.assert_called_once()

    def test_non_interactive_without_force_raises_safety_error(self, mock_console):
        ctx = SafetyContext(non_interactive=True, force=False)
        spec = get_write_spec("network rename")

        with pytest.raises(SafetyError) as exc_info:
            require_write_confirmation(spec, "network", ctx=ctx, console=mock_console)

        assert exc_info.value.exit_code == ExitCode.SAFETY_RAIL

    def test_default_ctx_and_console_are_created_when_omitted(self):
        spec = get_write_spec("eero led on")

        result = require_write_confirmation(spec, "Living Room")

        assert result is True


# ========================== Security-toggle getattr-dispatch coverage ==========================


class TestSecurityToggleDispatchCoverage:
    """Regression coverage for the `getattr(client, api_method)` dynamic
    dispatch in `network/security.py` (security-review follow-up).

    The source-walking completeness test above (and the SDK's own mypy
    checks) only see literal `await client.<verb>(` call sites. The five
    security toggles (wpa3, band-steering, upnp, ipv6, thread) call through
    `method = getattr(client, api_method); await method(...)`, where
    `api_method` is a function parameter, not a literal at the call site --
    invisible to any regex over `await client\\.`. This is exactly the shape
    that let the string-dispatch mypy blind spot ship in eero-api 7→8
    (migration plan §2.4). These tests instead ground themselves in the
    *other* place the toggle inventory is a literal: the
    `_make_security_toggle(name, method, display)` registration calls at
    the bottom of `network/security.py`.

    What fails if a toggle is unwired: a new call like
    `_make_security_toggle("newsetting", "set_new", "New")` reaches
    `_set_security_setting`, which calls
    `get_write_spec(f"network security {setting_name} {action}")` before
    doing anything else (including before the confirmation prompt) --
    `get_write_spec` raises `KeyError` for any command path not in
    `WRITE_SPECS`, so an unregistered toggle fails loudly and immediately,
    never silently reaching `getattr`/the write. `test_unwired_toggle_fails_loudly_via_get_write_spec`
    proves this by registering exactly such a throwaway toggle and
    confirming it raises instead of silently writing.
    """

    @staticmethod
    def _registered_toggles():
        """Extract (setting_name, sdk_method) pairs from the literal
        `_make_security_toggle(...)` calls in network/security.py -- the
        actual, ground-truth toggle inventory, not a hand-maintained list
        that could drift from it.
        """
        import inspect
        import re

        from eeroctl.commands.network import security as security_module

        source = inspect.getsource(security_module)
        pattern = re.compile(r'_make_security_toggle\(\s*"([^"]+)"\s*,\s*"(set_\w+)"')
        return pattern.findall(source)

    def test_every_registered_toggle_has_both_enable_and_disable_specs(self):
        toggles = self._registered_toggles()
        assert toggles, "No _make_security_toggle(...) calls found -- extraction regex is stale"

        for setting_name, _method in toggles:
            for action in ("enable", "disable"):
                command = f"network security {setting_name} {action}"
                assert command in WRITE_SPECS, (
                    f"{command!r} (from _make_security_toggle({setting_name!r}, ...)) "
                    "has no WriteSpec"
                )

    def test_registered_toggle_count_matches_expected(self):
        """Pins the toggle inventory so a newly added toggle is caught here
        (and its coverage checked above) rather than silently expanding the
        getattr-dispatch blind spot."""
        toggles = self._registered_toggles()
        assert {name for name, _ in toggles} == {
            "wpa3",
            "band-steering",
            "upnp",
            "ipv6",
            "thread",
        }

    def test_unwired_toggle_fails_loudly_via_get_write_spec(self):
        """Proof: an unregistered toggle raises KeyError from get_write_spec
        before any confirmation prompt or SDK call -- it cannot silently
        dispatch an unconfirmed, unregistered write."""
        from eeroctl.commands.network.security import _set_security_setting
        from eeroctl.context import EeroCliContext

        ctx = click.Context(click.Command("bogus"))
        ctx.obj = EeroCliContext()

        with pytest.raises(KeyError):
            _set_security_setting(ctx, "bogus-unregistered", "set_bogus", "Bogus", True, True)
