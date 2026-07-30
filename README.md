<!-- SPDX-License-Identifier: MIT -->

# leafwiki-mcp

An MCP server that lets compatible clients discover, read, organize, revise, favorite, create,
edit, and delete content in a [LeafWiki](https://github.com/perstarkse/leafwiki) instance.

## Status

The project is at version 0.1.0 and is under early development. It runs as a synchronous MCP
server over stdio. Installation from PyPI is not currently documented or supported; run it from
GitHub directly or from a source checkout.

## Prerequisites

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)

## Installation

Choose the method that matches how you plan to use the server. All methods run the same
`leafwiki-mcp` command over stdio.

### Run directly from GitHub (recommended)

Use `uvx` to run the server directly from the GitHub repository without cloning it or installing
it permanently:

```bash
uvx --from git+https://github.com/ipapadop/leafwiki-mcp.git leafwiki-mcp
```

`uvx` creates an isolated environment and caches downloaded dependencies for later runs.

### Install as a persistent tool

Install the server from GitHub when you want the `leafwiki-mcp` command to remain available on
your `PATH`:

```bash
uv tool install git+https://github.com/ipapadop/leafwiki-mcp.git
leafwiki-mcp
```

If `uv` reports that its tool directory is not on `PATH`, run `uv tool update-shell` and restart
your shell.

### Run from a source checkout

Clone over HTTPS:

```bash
git clone https://github.com/ipapadop/leafwiki-mcp.git
cd leafwiki-mcp
uv sync
```

Or clone over SSH:

```bash
git clone git@github.com:ipapadop/leafwiki-mcp.git
cd leafwiki-mcp
uv sync
```

## Configuration

The server accepts command-line options or equivalent environment variables:

| Option | Environment variable | Default |
| --- | --- | --- |
| `--url` | `LEAFWIKI_URL` | `http://localhost:8080` |
| `--username` | `LEAFWIKI_USERNAME` | empty |
| `--password` | `LEAFWIKI_PASSWORD` | empty |
| `--read-only` | `LEAFWIKI_READ_ONLY` | `false` |

Credentials are unnecessary when authentication is disabled. Accounts requiring
TOTP are not supported; use a dedicated editor account without TOTP.

The password in the MCP client example below is stored directly in that client's configuration.
Protect the configuration as you would any other credential. For an authentication-disabled
LeafWiki instance, omit `LEAFWIKI_USERNAME` and `LEAFWIKI_PASSWORD` entirely.

Set `LEAFWIKI_READ_ONLY=true` or pass `--read-only` to register only discovery and retrieval
tools. The environment variable accepts `true`/`false`, `1`/`0`, `yes`/`no`, and `on`/`off`
case-insensitively. Read-only mode provides defense in depth against accidental changes; it does
not replace LeafWiki's server-side authorization or appropriately scoped credentials.

## Running

If you installed `leafwiki-mcp` as a persistent tool, start it with:

```bash
leafwiki-mcp
```

From a source checkout, start it with:

```bash
uv run leafwiki-mcp
```

In normal use, an MCP client starts the server for you. Use the configuration that matches your
installation method.

### Directly from GitHub (recommended)

```json
{
  "mcpServers": {
    "leafwiki": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ipapadop/leafwiki-mcp.git",
        "leafwiki-mcp"
      ],
      "env": {
        "LEAFWIKI_URL": "https://wiki.example.com",
        "LEAFWIKI_USERNAME": "mcp-editor",
        "LEAFWIKI_PASSWORD": "replace-me"
      }
    }
  }
}
```

### Persistent tool installation

```json
{
  "mcpServers": {
    "leafwiki": {
      "command": "leafwiki-mcp",
      "env": {
        "LEAFWIKI_URL": "https://wiki.example.com",
        "LEAFWIKI_USERNAME": "mcp-editor",
        "LEAFWIKI_PASSWORD": "replace-me"
      }
    }
  }
}
```

### Source checkout

Replace `/absolute/path/to/leafwiki-mcp` with the location of your clone:

```json
{
  "mcpServers": {
    "leafwiki": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/leafwiki-mcp",
        "run",
        "leafwiki-mcp"
      ],
      "env": {
        "LEAFWIKI_URL": "https://wiki.example.com",
        "LEAFWIKI_USERNAME": "mcp-editor",
        "LEAFWIKI_PASSWORD": "replace-me"
      }
    }
  }
}
```

The server always exposes these discovery and retrieval tools over stdio:

- `search_pages`: search page text and tags with pagination
- `get_page`: retrieve Markdown content and metadata by ID or path
- `browse_tree`: browse the page hierarchy with an optional depth limit
- `get_page_links`: retrieve backlinks, outgoing links, and broken links
- `list_tags`: discover tags and their usage counts
- `find_pages_by_property`: find pages by structured property metadata
- `list_page_revisions`: list revision history when revisions are enabled
- `get_page_revision`: retrieve a historical page snapshot when revisions are enabled
- `compare_page_revisions`: compare two historical snapshots
- `get_indexing_status`: inspect full-text indexing state
- `list_property_keys`, `find_page_by_title`, `lookup_path`, and `suggest_slug`: discover page metadata and paths
- `list_favorites`: list personal bookmarks

In the default read-write mode, the server also exposes these mutation tools:

- `move_page`, `copy_page`, `ensure_path`, `convert_page`, and `pin_page`: organize pages
- `add_favorite` and `remove_favorite`: change personal bookmarks
- `append_to_page`, `update_page_tags`, and `update_page_properties`: make focused page updates
- `sort_pages`: set the ordering of children under a page
- `add_page`, `edit_page`, and `delete_page`: mutate pages using optimistic concurrency

Tools that select a page accept an ID or slash-separated path and prefer a non-empty ID when both
are supplied. Revision tools require revisions to be enabled in LeafWiki. Favorites require an
authenticated user when authentication is enabled.

Page edits and deletions use LeafWiki versions for optimistic concurrency. A conflict is returned
as an error so callers can re-read the page and retry deliberately. Deletion is non-recursive by
default; recursive deletion must be requested explicitly. Creating a page with content, tags, or
properties performs a create followed by a versioned update, so creation may succeed even if the
follow-up update fails.

## Troubleshooting

- **Cannot connect:** confirm `LEAFWIKI_URL` includes `http://` or `https://`, points to a running
  LeafWiki instance, and is reachable from the MCP client process.
- **Authentication required:** set both `LEAFWIKI_USERNAME` and `LEAFWIKI_PASSWORD`, or omit them
  when LeafWiki reports that authentication is disabled.
- **TOTP required:** TOTP accounts are unsupported. Use a dedicated editor account without TOTP.
- **Revision request fails:** confirm revisions are enabled in the LeafWiki instance.
- **Update or deletion conflicts:** re-read the page to obtain its current version, review the
  intervening change, and retry deliberately.

## Development

The tests use mocked HTTP transports and clients. They do not require a live LeafWiki instance,
network access, or real credentials.

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The `Quality` GitHub Actions workflow runs Ruff lint, Ruff formatting verification, Pyright, and
Pytest for every pull request, every push to `main`, and manual dispatches. Run the same commands
locally before pushing.

## Project links

- [Source repository](https://github.com/ipapadop/leafwiki-mcp)
- [Issue tracker](https://github.com/ipapadop/leafwiki-mcp/issues)

## License

This project is licensed under the [MIT License](LICENSE).
