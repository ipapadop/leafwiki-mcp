# SPDX-License-Identifier: MIT

"""Tests for LeafWiki MCP command-line configuration."""

from unittest.mock import MagicMock, Mock

import pytest

from leafwiki_mcp import __main__ as cli
from leafwiki_mcp.__main__ import build_parser


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


def test_read_only_flag_overrides_false_environment_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command-line flag should enable read-only mode over a false environment default."""
    monkeypatch.setenv("LEAFWIKI_READ_ONLY", "false")

    arguments = build_parser().parse_args(["--read-only"])

    assert arguments.read_only is True


def test_read_only_rejects_invalid_environment_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrecognized environment value should fail argument parsing."""
    monkeypatch.setenv("LEAFWIKI_READ_ONLY", "sometimes")

    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_main_disables_write_tool_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The read-only CLI flag should disable write tools in the MCP server."""
    client = Mock()
    client_context = MagicMock()
    client_context.__enter__.return_value = client
    client_class = Mock(return_value=client_context)
    mcp_server = Mock()
    create_server = Mock(return_value=mcp_server)
    monkeypatch.setattr(cli, "LeafWikiClient", client_class)
    monkeypatch.setattr(cli, "create_server", create_server)

    cli.main(["--url", "https://wiki.example.test", "--read-only"])

    client.authenticate.assert_called_once_with()
    create_server.assert_called_once_with(client, read_write=False)
    mcp_server.run.assert_called_once_with(transport="stdio")
