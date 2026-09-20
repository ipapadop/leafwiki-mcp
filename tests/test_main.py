# SPDX-License-Identifier: MIT

"""Tests for LeafWiki MCP command-line configuration."""

from unittest.mock import MagicMock, Mock

import pytest

from leafwiki_mcp import __main__ as cli
from leafwiki_mcp.__main__ import build_parser
from leafwiki_mcp.client import LeafWikiConnectionError, LeafWikiError


def install_fake_server(monkeypatch: pytest.MonkeyPatch, client: Mock) -> Mock:
    """Replace the client and server factories used by ``main`` with test doubles.

    Args:
        monkeypatch: Fixture used to patch the command-line module.
        client: Client double returned by the patched client context manager.

    Returns:
        Mock server factory whose ``return_value`` is the MCP server ``main`` runs.
    """
    client_context = MagicMock()
    client_context.__enter__.return_value = client
    monkeypatch.setattr(cli, "LeafWikiClient", Mock(return_value=client_context))
    create_server = Mock(return_value=Mock())
    monkeypatch.setattr(cli, "create_server", create_server)
    return create_server


def test_read_only_defaults_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The server should retain read-write behavior when no setting is supplied."""
    monkeypatch.delenv("LEAFWIKI_READ_ONLY", raising=False)

    arguments = build_parser().parse_args([])

    assert arguments.read_only is False


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_read_only_accepts_true_environment_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Supported true spellings should enable read-only mode."""
    monkeypatch.setenv("LEAFWIKI_READ_ONLY", value)

    arguments = build_parser().parse_args([])

    assert arguments.read_only is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_read_only_accepts_false_environment_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Supported false spellings should retain read-write mode."""
    monkeypatch.setenv("LEAFWIKI_READ_ONLY", value)

    arguments = build_parser().parse_args([])

    assert arguments.read_only is False


def test_read_only_rejects_invalid_environment_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrecognized environment value should fail argument parsing."""
    monkeypatch.setenv("LEAFWIKI_READ_ONLY", "sometimes")

    with pytest.raises(SystemExit):
        build_parser().parse_args([])


@pytest.mark.parametrize(
    ("environment_value", "option", "expected_read_write"),
    [("false", "--read-only", False), ("true", "--no-read-only", True)],
)
def test_main_cli_mode_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
    environment_value: str,
    option: str,
    expected_read_write: bool,
) -> None:
    """An explicit CLI mode should override the environment-configured mode."""
    monkeypatch.setenv("LEAFWIKI_READ_ONLY", environment_value)
    client = Mock()
    create_server = install_fake_server(monkeypatch, client)

    cli.main(["--url", "https://wiki.example.test", option])

    create_server.assert_called_once_with(client, read_write=expected_read_write)


def test_main_serves_when_leafwiki_is_unreachable_at_startup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A temporarily unreachable instance should not prevent the server from starting."""
    client = Mock()
    client.authenticate.side_effect = LeafWikiConnectionError("Connect to LeafWiki: refused")
    create_server = install_fake_server(monkeypatch, client)

    cli.main(["--url", "https://wiki.example.test"])

    create_server.return_value.run.assert_called_once_with(transport="stdio")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Connect to LeafWiki: refused" in captured.err


def test_main_stops_when_authentication_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A credential or TOTP failure should stop startup instead of serving broken tools."""
    client = Mock()
    client.authenticate.side_effect = LeafWikiError("LeafWiki account requires TOTP")
    create_server = install_fake_server(monkeypatch, client)

    with pytest.raises(LeafWikiError, match="requires TOTP"):
        cli.main(["--url", "https://wiki.example.test"])

    create_server.return_value.run.assert_not_called()
