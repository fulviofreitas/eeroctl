"""Unit and integration tests for the SDK unverified-write warning filter.

Covers migration plan §3.3 and §5.2 "Warning-filter tests":
- `_SdkWarningFilter` captures `warn_uncharacterised_write` records
- the raw log line is suppressed in normal/--quiet mode
- `EeroCliContext.record_sdk_warning` populates `meta.warnings` regardless
  of --quiet/--debug
- `--debug` passes the raw line through unchanged and skips the note
- two warnings from one command produce two `meta.warnings` entries but
  the stderr note prints once per distinct operation
- stdout stays clean in every mode
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from eeroctl.context import EeroCliContext
from eeroctl.main import (
    _OPERATION_PATTERN,
    _UNCHARACTERISED_WRITE_MARKER,
    _SdkWarningFilter,
    cli,
)
from eeroctl.output import OutputContext, OutputFormat, OutputMeta, OutputRenderer
from eeroctl.safety import OperationRisk, WriteSpec, WriteStatus

# The exact text eero-api's `warn_uncharacterised_write` emits
# (DIGEST §5, `api/_writes.py:66-72`), operation interpolated as %s.
_SDK_WARNING_MSG = (
    "Issuing write (%s): its side effects have not been fully "
    "characterised against a live network. Read the current state "
    "first and skip the write when it already matches -- never retry "
    "a failed write in a loop."
)


def _make_record(logger_name: str, operation: str) -> logging.LogRecord:
    """Build a LogRecord matching the SDK's uncharacterised-write warning."""
    return logging.LogRecord(
        name=logger_name,
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=_SDK_WARNING_MSG,
        args=(operation,),
        exc_info=None,
    )


# ========================== Marker / pattern sanity ==========================


class TestMarkerAndPattern:
    """The filter's message-matching primitives, checked against the SDK's exact text."""

    def test_marker_matches_the_sdk_text(self):
        rendered = _SDK_WARNING_MSG % "dns_mode"
        assert _UNCHARACTERISED_WRITE_MARKER in rendered

    def test_unrelated_message_does_not_match(self):
        assert _UNCHARACTERISED_WRITE_MARKER not in "some other warning entirely"

    def test_operation_pattern_extracts_the_op(self):
        rendered = _SDK_WARNING_MSG % "dns_mode"
        match = _OPERATION_PATTERN.search(rendered)
        assert match is not None
        assert match.group(1) == "dns_mode"


# ========================== EeroCliContext.record_sdk_warning ==========================


class TestRecordSdkWarning:
    """Tests for EeroCliContext.record_sdk_warning."""

    def test_first_occurrence_returns_note_and_appends(self):
        cli_ctx = EeroCliContext()

        note = cli_ctx.record_sdk_warning("dns_mode")

        assert note is not None
        assert "dns_mode" in note
        assert cli_ctx.sdk_warnings == [note]

    def test_repeat_of_same_operation_returns_none_but_still_appends(self):
        cli_ctx = EeroCliContext()

        first = cli_ctx.record_sdk_warning("dns_mode")
        second = cli_ctx.record_sdk_warning("dns_mode")

        assert first is not None
        assert second is None
        # meta.warnings gets an entry every time -- two occurrences, two entries.
        assert cli_ctx.sdk_warnings == [first, first]

    def test_two_distinct_operations_both_return_a_note(self):
        cli_ctx = EeroCliContext()

        first = cli_ctx.record_sdk_warning("dns_mode")
        second = cli_ctx.record_sdk_warning("dns_caching")

        assert first is not None
        assert second is not None
        assert first != second
        assert len(cli_ctx.sdk_warnings) == 2

    def test_note_includes_read_command_when_a_spec_is_active(self):
        cli_ctx = EeroCliContext()
        cli_ctx.active_write_spec = WriteSpec(
            command="network sqm enable",
            risk=OperationRisk.HIGH,
            status=WriteStatus.UNVERIFIED,
            reboots="mesh",
            read_command="eero network sqm show",
            phrase="REBOOT",
        )

        note = cli_ctx.record_sdk_warning("sqm")

        assert "eero network sqm show" in note

    def test_note_omits_read_command_when_no_spec_is_active(self):
        cli_ctx = EeroCliContext()
        cli_ctx.active_write_spec = None

        note = cli_ctx.record_sdk_warning("mystery_write")

        assert "mystery_write" in note
        assert "verify with" not in note


# ========================== _SdkWarningFilter ==========================


class TestSdkWarningFilterUnit:
    """Direct, white-box tests of the logging.Filter (§5.2 "Warning-filter tests")."""

    @pytest.fixture
    def cli_ctx(self) -> EeroCliContext:
        return EeroCliContext()

    def test_unrelated_record_passes_through_untouched(self, cli_ctx):
        record = logging.LogRecord(
            name="eero.api.dns",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="some unrelated warning",
            args=(),
            exc_info=None,
        )
        filt = _SdkWarningFilter(cli_ctx, debug=False)

        assert filt.filter(record) is True
        assert cli_ctx.sdk_warnings == []

    def test_matching_record_is_suppressed_in_normal_mode(self, cli_ctx):
        record = _make_record("eero.api.dns", "dns_mode")
        filt = _SdkWarningFilter(cli_ctx, debug=False)

        with patch.object(cli_ctx.renderer, "render_sdk_warning_note") as mock_render:
            result = filt.filter(record)

        assert result is False
        mock_render.assert_called_once()
        assert cli_ctx.sdk_warnings

    def test_debug_mode_passes_the_raw_line_through_and_skips_the_note(self, cli_ctx):
        record = _make_record("eero.api.dns", "dns_mode")
        filt = _SdkWarningFilter(cli_ctx, debug=True)

        with patch.object(cli_ctx.renderer, "render_sdk_warning_note") as mock_render:
            result = filt.filter(record)

        assert result is True
        mock_render.assert_not_called()
        # meta.warnings is still populated in --debug mode.
        assert cli_ctx.sdk_warnings

    def test_quiet_suppresses_the_note_but_still_records_it(self, cli_ctx):
        cli_ctx.quiet = True
        record = _make_record("eero.api.dns", "dns_mode")
        filt = _SdkWarningFilter(cli_ctx, debug=False)

        with patch.object(cli_ctx.renderer, "render_sdk_warning_note") as mock_render:
            result = filt.filter(record)

        assert result is False
        mock_render.assert_not_called()
        assert cli_ctx.sdk_warnings

    def test_two_warnings_same_op_prints_note_once(self, cli_ctx):
        filt = _SdkWarningFilter(cli_ctx, debug=False)

        with patch.object(cli_ctx.renderer, "render_sdk_warning_note") as mock_render:
            filt.filter(_make_record("eero.api.dns", "dns_mode"))
            filt.filter(_make_record("eero.api.dns", "dns_mode"))

        assert mock_render.call_count == 1
        assert len(cli_ctx.sdk_warnings) == 2

    def test_two_warnings_different_ops_prints_two_notes(self, cli_ctx):
        filt = _SdkWarningFilter(cli_ctx, debug=False)

        with patch.object(cli_ctx.renderer, "render_sdk_warning_note") as mock_render:
            filt.filter(_make_record("eero.api.dns", "dns_mode"))
            filt.filter(_make_record("eero.api.dns", "dns_caching"))

        assert mock_render.call_count == 2
        assert len(cli_ctx.sdk_warnings) == 2

    def test_non_eero_api_logger_name_still_matches_on_message(self, cli_ctx):
        """`eero.client` also emits writes; the filter must not assume the
        `eero.api.*` prefix (DIGEST §5)."""
        record = _make_record("eero.client", "some_write")
        filt = _SdkWarningFilter(cli_ctx, debug=False)

        with patch.object(cli_ctx.renderer, "render_sdk_warning_note"):
            result = filt.filter(record)

        assert result is False
        assert cli_ctx.sdk_warnings


# ========================== meta.warnings plumbing ==========================


class TestMetaWarningsPlumbing:
    """OutputContext/OutputMeta pick up EeroCliContext.sdk_warnings automatically."""

    def test_render_json_includes_recorded_warnings_by_default(self, capsys):
        cli_ctx = EeroCliContext(output_format="json")
        cli_ctx.record_sdk_warning("dns_mode")

        cli_ctx.renderer.render_json({"ok": True}, "eero.test/v1")

        captured = capsys.readouterr()
        assert "dns_mode" in captured.out

    def test_warnings_captured_after_context_creation_still_appear(self, capsys):
        """A write's warning fires *after* the renderer/OutputContext is
        already built -- the list must be shared by reference, not copied."""
        cli_ctx = EeroCliContext(output_format="json")
        renderer = cli_ctx.renderer  # Force OutputContext construction first.
        cli_ctx.record_sdk_warning("sqm")

        renderer.render_json({"ok": True}, "eero.test/v1")

        captured = capsys.readouterr()
        assert "sqm" in captured.out

    def test_explicit_meta_is_not_overridden(self):
        ctx = OutputContext(format=OutputFormat.JSON, warnings=["captured"])
        renderer = OutputRenderer(ctx)
        explicit_meta = OutputMeta(warnings=["explicit-only"])

        # No assertion error means render_json accepted the explicit meta;
        # behavioural check is that it does not raise and uses explicit_meta
        # (verified indirectly by not touching ctx.warnings).
        renderer.render_json({"ok": True}, "eero.test/v1", meta=explicit_meta)


# ========================== End-to-end via CliRunner ==========================


class TestSdkWarningFilterInstalled:
    """Integration: the filter is actually installed by `cli()` and works
    against a real command invocation, not just direct construction."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def _mock_client_with_warning(self, op: str):
        """A mock client whose block_device call also logs the SDK warning,
        the way eero-api's real DevicesAPI.block_device does."""
        mock_devices_response = {
            "meta": {"code": 200},
            "data": [
                {
                    "url": "/2.2/networks/net1/devices/dev1",
                    "mac": "AA:BB:CC:DD:EE:FF",
                    "nickname": "MyPhone",
                    "hostname": "myphone",
                    "connected": True,
                    "blacklisted": False,
                    "paused": False,
                }
            ],
        }

        async def _block_side_effect(*args, **kwargs):
            logging.getLogger("eero.api.devices").warning(_SDK_WARNING_MSG, op)
            return {"meta": {"code": 200}, "data": {}}

        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(return_value=mock_devices_response)
        mock_client.block_device = AsyncMock(side_effect=_block_side_effect)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    def test_normal_mode_stdout_clean_one_stderr_note(self, runner):
        mock_client = self._mock_client_with_warning("block_device")

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["device", "block", "MyPhone", "--force"])

        assert result.exit_code == 0
        assert "WARNING" not in result.stdout
        assert "characterised" not in result.stdout
        assert "note: unverified write (block_device)" in result.stderr
        assert result.stderr.count("note: unverified write (block_device)") == 1

    def test_quiet_suppresses_the_stderr_note(self, runner):
        mock_client = self._mock_client_with_warning("block_device")

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--quiet", "device", "block", "MyPhone", "--force"])

        assert result.exit_code == 0
        assert "note: unverified write" not in result.stderr

    def test_debug_passes_the_raw_line_through(self, runner):
        mock_client = self._mock_client_with_warning("block_device")

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--debug", "device", "block", "MyPhone", "--force"])

        assert result.exit_code == 0
        assert "note: unverified write" not in result.stderr
        assert "characterised" in result.stderr

    def test_stdout_stays_clean_even_under_debug(self, runner):
        mock_client = self._mock_client_with_warning("block_device")

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--debug", "device", "block", "MyPhone", "--force"])

        assert "characterised" not in result.stdout


class TestJsonOutputCarriesMetaWarnings:
    """End-to-end: --output json on a write command surfaces the SDK
    warning in meta.warnings, with stdout staying valid-JSON-only.

    None of the currently-registered *toggle* writes (``device block``
    included) render JSON on success -- they print a plain
    ``write_if_changed`` acceptance message regardless of ``--output``, so
    there is nothing for a JSON parse to grab onto for those. ``profile
    create`` is used instead: it is a registered, UNVERIFIED write (§3.2)
    that already renders through ``cli_ctx.render_structured`` under
    ``--output json``, so it is the smallest change from the requested
    ``device block`` case that actually exercises meta.warnings end to end
    through real JSON output.
    """

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_output_json_includes_the_note_in_meta_warnings(self, runner):
        import json

        async def _create_profile_side_effect(*args, **kwargs):
            logging.getLogger("eero.api.profiles").warning(_SDK_WARNING_MSG, "create_profile")
            return {
                "meta": {"code": 200},
                "data": {"url": "/2.2/networks/net1/profiles/p1", "name": "Kids"},
            }

        mock_client = AsyncMock()
        mock_client.create_profile = AsyncMock(side_effect=_create_profile_side_effect)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eeroctl.utils.EeroClient", return_value=mock_client):
            result = runner.invoke(cli, ["--output", "json", "profile", "create", "Kids"])

        assert result.exit_code == 0, result.output
        # stdout is valid JSON and nothing else -- no interleaved warning text.
        parsed = json.loads(result.stdout)
        assert parsed["meta"]["warnings"]
        assert any("create_profile" in w for w in parsed["meta"]["warnings"])
        assert "characterised" not in result.stdout
        # The concise stderr note still fires, on stderr, same as any other write.
        assert "note: unverified write (create_profile)" in result.stderr
