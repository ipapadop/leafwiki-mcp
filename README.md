# leafwiki-mcp

An MCP server that lets compatible clients read, search, create, edit, and delete pages in a
[LeafWiki](https://github.com/perstarkse/leafwiki) instance.

## Installation

Install the project with `uv`:

```bash
uv sync
```

## Configuration

The server accepts command-line options or equivalent environment variables:

| Option | Environment variable | Default |
| --- | --- | --- |
| `--url` | `LEAFWIKI_URL` | `http://localhost:8080` |
| `--username` | `LEAFWIKI_USERNAME` | empty |
| `--password` | `LEAFWIKI_PASSWORD` | empty |

Credentials are unnecessary when authentication is disabled. Accounts requiring
TOTP are not supported; use a dedicated editor account without TOTP.

## Running

```bash
uv run leafwiki-mcp
```

Example MCP client configuration:

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

The server exposes these tools over stdio:

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
- `move_page`, `copy_page`, `ensure_path`, `convert_page`, and `pin_page`: organize pages
- `add_favorite`, `remove_favorite`, and `list_favorites`: manage personal bookmarks
- `append_to_page`, `update_page_tags`, and `update_page_properties`: make focused page updates
- `sort_pages`: set the ordering of children under a page
- `add_page`, `edit_page`, and `delete_page`: mutate pages using optimistic concurrency

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```
