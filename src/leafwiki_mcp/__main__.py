# SPDX-License-Identifier: MIT

"""Command-line entry point for the LeafWiki MCP server."""

import argparse
import os
from collections.abc import Sequence

from leafwiki_mcp.client import LeafWikiClient
from leafwiki_mcp.server import create_server


def _parse_boolean(value: str) -> bool:
    """Parse a boolean configuration value.

    Args:
        value: Case-insensitive boolean spelling.

    Returns:
        Parsed boolean value.

    Raises:
        ValueError: If the value is not a supported boolean spelling.
    """
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        Parser containing the supported LeafWiki connection options.
    """
    parser = argparse.ArgumentParser(description="Expose LeafWiki page mutations over MCP stdio.")
    parser.add_argument(
        "--url",
        default=os.getenv("LEAFWIKI_URL", "http://localhost:8080"),
        help="LeafWiki server URL",
    )
    parser.add_argument(
        "--username", default=os.getenv("LEAFWIKI_USERNAME", ""), help="LeafWiki username"
    )
    parser.add_argument(
        "--password", default=os.getenv("LEAFWIKI_PASSWORD", ""), help="LeafWiki password"
    )
    try:
        read_only_default = _parse_boolean(os.getenv("LEAFWIKI_READ_ONLY", "false"))
    except ValueError as error:
        parser.error(f"LEAFWIKI_READ_ONLY: {error}")
    parser.add_argument(
        "--read-only",
        action=argparse.BooleanOptionalAction,
        default=read_only_default,
        help="register only tools that do not mutate LeafWiki state",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Authenticate with LeafWiki and serve MCP requests over stdio.

    Args:
        argv: Optional command-line arguments. Uses the process arguments when omitted.
    """
    arguments = build_parser().parse_args(argv)
    with LeafWikiClient(arguments.url, arguments.username, arguments.password) as client:
        client.authenticate()
        create_server(client, read_write=not arguments.read_only).run(transport="stdio")


if __name__ == "__main__":
    main()
