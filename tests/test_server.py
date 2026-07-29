# SPDX-License-Identifier: MIT

"""Tests for LeafWiki MCP operations."""

from typing import Any
from unittest.mock import Mock

from leafwiki_mcp.client import LeafWikiClient, Page
from leafwiki_mcp.server import LeafWikiTools


def make_page(**overrides: Any) -> Page:
    """Build a page for tool tests.

    Args:
        **overrides: Page fields that replace the representative defaults.

    Returns:
        Page model populated with test values.
    """
    values: dict[str, Any] = {
        "id": "page-1",
        "title": "Old title",
        "slug": "old-title",
        "path": "old-title",
        "version": "v1",
        "kind": "page",
        "content": "Old content",
        "tags": ["old"],
        "properties": {"status": "draft"},
    }
    values.update(overrides)
    return Page(**values)


def test_edit_page_preserves_omitted_fields() -> None:
    """Editing one field should retain all other current page values."""
    client = Mock(spec=LeafWikiClient)
    current = make_page()
    updated = make_page(title="New title", version="v2")
    client.get_page.return_value = current
    client.update_page.return_value = updated

    result = LeafWikiTools(client).edit_page(path="old-title", title="New title")

    client.get_page.assert_called_once_with(page_id="", path="old-title")
    client.update_page.assert_called_once_with(
        current,
        title="New title",
        slug="old-title",
        content="Old content",
        tags=["old"],
        properties={"status": "draft"},
    )
    assert result["version"] == "v2"


def test_delete_page_fetches_current_page_before_delete() -> None:
    """Deletion should resolve the selector before issuing the versioned request."""
    client = Mock(spec=LeafWikiClient)
    current = make_page()
    client.get_page.return_value = current
    client.delete_page.return_value = {"deleted": True, "id": current.id, "path": current.path}

    result = LeafWikiTools(client).delete_page(id="page-1", recursive=True)

    client.get_page.assert_called_once_with(page_id="page-1", path="")
    client.delete_page.assert_called_once_with(current, recursive=True)
    assert result["deleted"] is True


def test_get_page_returns_serializable_page() -> None:
    """The get-page tool should expose the complete page response."""
    client = Mock(spec=LeafWikiClient)
    client.get_page.return_value = make_page()

    result = LeafWikiTools(client).get_page(path="old-title")

    client.get_page.assert_called_once_with(page_id="", path="old-title")
    assert result["content"] == "Old content"
    assert result["properties"] == {"status": "draft"}


def test_read_tools_forward_arguments_to_client() -> None:
    """Read tools should remain thin wrappers over the LeafWiki client."""
    client = Mock(spec=LeafWikiClient)
    client.search_pages.return_value = {"items": []}
    client.browse_tree.return_value = {"id": "root"}
    client.get_page_links.return_value = {"backlinks": []}
    client.list_tags.return_value = [{"tag": "agent", "count": 1}]
    client.find_pages_by_property.return_value = []
    client.list_page_revisions.return_value = {"revisions": []}
    client.get_page_revision.return_value = {"content": "Earlier"}
    tools = LeafWikiTools(client)

    assert tools.search_pages("memory", ["agent"], 5, 10) == {"items": []}
    assert tools.browse_tree(2) == {"id": "root"}
    assert tools.get_page_links(path="page") == {"backlinks": []}
    assert tools.list_tags("ag", ["docs"], 10)[0]["tag"] == "agent"
    assert tools.find_pages_by_property("status", "approved") == []
    assert tools.list_page_revisions(path="page", cursor="next", limit=10) == {"revisions": []}
    assert tools.get_page_revision("rev-1", path="page") == {"content": "Earlier"}

    client.search_pages.assert_called_once_with(query="memory", tags=["agent"], offset=5, limit=10)
    client.browse_tree.assert_called_once_with(depth=2)
    client.get_page_links.assert_called_once_with(page_id="", path="page")
    client.list_tags.assert_called_once_with(query="ag", selected=["docs"], limit=10)
    client.find_pages_by_property.assert_called_once_with(key="status", value="approved")
    client.list_page_revisions.assert_called_once_with(
        page_id="", path="page", cursor="next", limit=10
    )
    client.get_page_revision.assert_called_once_with(revision_id="rev-1", page_id="", path="page")
