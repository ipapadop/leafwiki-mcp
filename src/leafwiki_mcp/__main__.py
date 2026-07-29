# SPDX-License-Identifier: MIT

"""Command-line entry point for the LeafWiki MCP server."""

import argparse
import os
from collections.abc import Sequence

from leafwiki_mcp.client import LeafWikiClient
from leafwiki_mcp.server import create_server


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
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Authenticate with LeafWiki and serve MCP requests over stdio.

    Args:
        argv: Optional command-line arguments. Uses the process arguments when omitted.
    """
    arguments = build_parser().parse_args(argv)
    with LeafWikiClient(arguments.url, arguments.username, arguments.password) as client:
        client.authenticate()
        create_server(client).run(transport="stdio")


if __name__ == "__main__":
    main()
