# SPDX-License-Identifier: MIT

"""MCP tool definitions for LeafWiki."""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from leafwiki_mcp.client import LeafWikiClient


class LeafWikiTools:
    """Operations exposed by the LeafWiki MCP server.

    Attributes:
        _client: Authenticated LeafWiki API client used by every tool.
    """

    def __init__(self, client: LeafWikiClient) -> None:
        """Initialize the operations with an authenticated LeafWiki client.

        Args:
            client: Client used to perform LeafWiki API operations.
        """
        self._client = client

    def add_page(
        self,
        title: str,
        slug: str,
        parent_id: str = "",
        kind: Literal["page", "section"] = "page",
        content: str | None = None,
        tags: list[str] | None = None,
        properties: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a page or section, optionally with content and metadata.

        Args:
            title: Display title for the new page.
            slug: URL path segment for the new page.
            parent_id: Parent identifier, or empty for the root.
            kind: Page kind, either ``page`` or ``section``.
            content: Optional Markdown content.
            tags: Optional tags.
            properties: Optional structured properties.

        Returns:
            JSON-compatible created page.
        """
        page = self._client.create_page(
            title=title,
            slug=slug,
            parent_id=parent_id,
            kind=kind,
            content=content,
            tags=tags,
            properties=properties,
        )
        return page.to_dict()

    def search_pages(
        self,
        query: str = "",
        tags: list[str] | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search pages by text and tags, returning excerpts and tag facets.

        Args:
            query: Full-text search query.
            tags: Optional tags used to filter results.
            offset: Zero-based result offset.
            limit: Maximum number of results.

        Returns:
            Search result object returned by LeafWiki.
        """
        return self._client.search_pages(query=query, tags=tags, offset=offset, limit=limit)

    def get_page(self, id: str = "", path: str = "") -> dict[str, Any]:
        """Get a page by ID or path, including content and metadata.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            JSON-compatible page.
        """
        return self._client.get_page(page_id=id, path=path).to_dict()

    def browse_tree(self, depth: int | None = None) -> dict[str, Any]:
        """Browse the page hierarchy, optionally limited to a depth.

        Args:
            depth: Optional maximum tree depth.

        Returns:
            LeafWiki page-tree object.
        """
        return self._client.browse_tree(depth=depth)

    def get_page_links(self, id: str = "", path: str = "") -> dict[str, Any]:
        """Get backlinks, outgoing links, and broken links for a page.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            Link information returned by LeafWiki.
        """
        return self._client.get_page_links(page_id=id, path=path)

    def list_tags(
        self,
        query: str = "",
        selected: list[str] | None = None,
        limit: int = 50,
    ) -> list[Any]:
        """List tags and usage counts, optionally filtering by name.

        Args:
            query: Optional tag-name filter.
            selected: Tags LeafWiki should retain in the result set.
            limit: Maximum number of tags.

        Returns:
            Tag objects returned by LeafWiki.
        """
        return self._client.list_tags(query=query, selected=selected, limit=limit)

    def find_pages_by_property(self, key: str, value: str = "") -> list[Any]:
        """Find pages carrying a property key and optional value.

        Args:
            key: Required property key.
            value: Optional property value to match.

        Returns:
            Matching page summaries.
        """
        return self._client.find_pages_by_property(key=key, value=value)

    def list_page_revisions(
        self,
        id: str = "",
        path: str = "",
        cursor: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        """List page revisions; requires revisions to be enabled.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.
            cursor: Optional pagination cursor.
            limit: Maximum number of revisions.

        Returns:
            Revision metadata and pagination information.
        """
        return self._client.list_page_revisions(page_id=id, path=path, cursor=cursor, limit=limit)

    def get_page_revision(self, revision_id: str, id: str = "", path: str = "") -> dict[str, Any]:
        """Get a page revision; requires revisions to be enabled.

        Args:
            revision_id: Revision identifier to retrieve.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            Historical page snapshot.
        """
        return self._client.get_page_revision(revision_id=revision_id, page_id=id, path=path)

    def compare_page_revisions(
        self,
        base_revision_id: str,
        target_revision_id: str,
        id: str = "",
        path: str = "",
    ) -> dict[str, Any]:
        """Compare two historical page snapshots.

        Args:
            base_revision_id: Revision used as the comparison base.
            target_revision_id: Revision compared with the base.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            Revision comparison returned by LeafWiki.
        """
        return self._client.compare_page_revisions(
            page_id=id,
            path=path,
            base_revision_id=base_revision_id,
            target_revision_id=target_revision_id,
        )

    def get_indexing_status(self) -> dict[str, Any]:
        """Get full-text search indexing status.

        Returns:
            Indexing status returned by LeafWiki.
        """
        return self._client.get_indexing_status()

    def list_property_keys(self, query: str = "", limit: int = 50) -> list[Any]:
        """List available property keys.

        Args:
            query: Optional property-key filter.
            limit: Maximum number of keys.

        Returns:
            Property-key objects returned by LeafWiki.
        """
        return self._client.list_property_keys(query=query, limit=limit)

    def find_page_by_title(self, title: str) -> dict[str, Any]:
        """Find pages by title.

        Args:
            title: Title to match.

        Returns:
            Title-match result returned by LeafWiki.
        """
        return self._client.find_page_by_title(title=title)

    def lookup_path(self, path: str) -> dict[str, Any]:
        """Resolve a path into tree segments.

        Args:
            path: Slash-separated page path to resolve.

        Returns:
            Existing and missing path segments.
        """
        return self._client.lookup_path(path=path)

    def suggest_slug(self, title: str, parent_id: str = "", current_id: str = "") -> dict[str, Any]:
        """Suggest an available slug for a title.

        Args:
            title: Title from which to derive a slug.
            parent_id: Parent used to determine availability.
            current_id: Existing page to exclude from conflicts.

        Returns:
            Slug suggestion returned by LeafWiki.
        """
        return self._client.suggest_slug(title=title, parent_id=parent_id, current_id=current_id)

    def move_page(
        self, id: str = "", path: str = "", parent_id: str = "", position: int | None = None
    ) -> dict[str, Any]:
        """Move a page under a new parent.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.
            parent_id: Destination parent identifier, or empty for root.
            position: Optional zero-based position under the parent.

        Returns:
            Serializable move confirmation.
        """
        return self._client.move_page(page_id=id, path=path, parent_id=parent_id, position=position)

    def copy_page(
        self,
        title: str,
        slug: str,
        id: str = "",
        path: str = "",
        target_parent_id: str = "",
    ) -> dict[str, Any]:
        """Copy a page and its assets.

        Args:
            title: Title for the copied page.
            slug: Slug for the copied page.
            id: Source page identifier, preferred when both selectors are supplied.
            path: Slash-separated source page path.
            target_parent_id: Destination parent identifier, or empty for root.

        Returns:
            JSON-compatible copied page.
        """
        return self._client.copy_page(
            page_id=id, path=path, title=title, slug=slug, target_parent_id=target_parent_id
        ).to_dict()

    def ensure_path(
        self, path: str, title: str, kind: Literal["page", "section"] = "page"
    ) -> dict[str, Any]:
        """Ensure a nested page path exists.

        Args:
            path: Slash-separated path to ensure.
            title: Title for the final node.
            kind: Kind for the final node, either ``page`` or ``section``.

        Returns:
            JSON-compatible final page.
        """
        return self._client.ensure_path(path=path, title=title, kind=kind).to_dict()

    def convert_page(
        self, target_kind: Literal["page", "section"], id: str = "", path: str = ""
    ) -> dict[str, Any]:
        """Convert a page to a section or a section to a page.

        Args:
            target_kind: Destination kind, either ``page`` or ``section``.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            Serializable conversion confirmation.
        """
        return self._client.convert_page(page_id=id, path=path, target_kind=target_kind)

    def add_favorite(self, id: str = "", path: str = "") -> dict[str, Any]:
        """Favorite a page for the authenticated user.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            Serializable favorite confirmation.
        """
        return self._client.add_favorite(page_id=id, path=path)

    def remove_favorite(self, id: str = "", path: str = "") -> dict[str, Any]:
        """Remove a page from the authenticated user's favorites.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            Serializable removal confirmation.
        """
        return self._client.remove_favorite(page_id=id, path=path)

    def list_favorites(self) -> list[Any]:
        """List the authenticated user's favorite pages.

        Returns:
            Favorite page summaries.
        """
        return self._client.list_favorites()

    def pin_page(self, pinned: bool = True, id: str = "", path: str = "") -> dict[str, Any]:
        """Pin or unpin a page.

        Args:
            pinned: Whether the page should be pinned.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            JSON-compatible updated page.
        """
        return self._client.pin_page(page_id=id, path=path, pinned=pinned).to_dict()

    def append_to_page(self, content: str, id: str = "", path: str = "") -> dict[str, Any]:
        """Append Markdown content to a page.

        Args:
            content: Markdown content to append.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            JSON-compatible updated page.
        """
        return self._client.append_to_page(page_id=id, path=path, content=content).to_dict()

    def update_page_tags(self, tags: list[str], id: str = "", path: str = "") -> dict[str, Any]:
        """Replace a page's tags.

        Args:
            tags: Complete replacement tag list.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            JSON-compatible updated page.
        """
        return self._client.update_page_tags(page_id=id, path=path, tags=tags).to_dict()

    def update_page_properties(
        self, properties: dict[str, str], id: str = "", path: str = ""
    ) -> dict[str, Any]:
        """Replace a page's properties.

        Args:
            properties: Complete replacement property mapping.
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.

        Returns:
            JSON-compatible updated page.
        """
        return self._client.update_page_properties(
            page_id=id, path=path, properties=properties
        ).to_dict()

    def sort_pages(self, parent_id: str, ordered_ids: list[str]) -> dict[str, Any]:
        """Set the child ordering under a parent page.

        Args:
            parent_id: Parent identifier, or empty for root.
            ordered_ids: Child identifiers in their desired order.

        Returns:
            Serializable sort confirmation.
        """
        return self._client.sort_pages(parent_id=parent_id, ordered_ids=ordered_ids)

    def edit_page(
        self,
        id: str = "",
        path: str = "",
        title: str | None = None,
        slug: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        properties: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Edit a page while preserving omitted fields.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.
            title: Optional replacement title; omitted values are preserved.
            slug: Optional replacement slug; omitted values are preserved.
            content: Optional replacement content; omitted values are preserved.
            tags: Optional replacement tags; omitted values are preserved.
            properties: Optional replacement properties; omitted values are preserved.

        Returns:
            JSON-compatible updated page.
        """
        current = self._client.get_page(page_id=id, path=path)
        updated = self._client.update_page(
            current,
            title=current.title if title is None else title,
            slug=current.slug if slug is None else slug,
            content=current.content if content is None else content,
            tags=current.tags if tags is None else tags,
            properties=current.properties if properties is None else properties,
        )
        return updated.to_dict()

    def delete_page(
        self, id: str = "", path: str = "", recursive: bool = False
    ) -> dict[str, str | bool]:
        """Delete a page after fetching its current version.

        Args:
            id: Page identifier, preferred when both selectors are supplied.
            path: Slash-separated page path.
            recursive: Whether to delete descendants recursively. Defaults to ``False``.

        Returns:
            Serializable deletion confirmation.
        """
        current = self._client.get_page(page_id=id, path=path)
        return self._client.delete_page(current, recursive=recursive)


def create_server(client: LeafWikiClient) -> FastMCP:
    """Create an MCP server backed by an authenticated LeafWiki client.

    Args:
        client: Authenticated client used by the registered tools.

    Returns:
        FastMCP server with every public LeafWiki tool registered.
    """
    server = FastMCP("leafwiki")
    tools = LeafWikiTools(client)
    server.tool()(tools.search_pages)
    server.tool()(tools.get_page)
    server.tool()(tools.browse_tree)
    server.tool()(tools.get_page_links)
    server.tool()(tools.list_tags)
    server.tool()(tools.find_pages_by_property)
    server.tool()(tools.list_page_revisions)
    server.tool()(tools.get_page_revision)
    server.tool()(tools.compare_page_revisions)
    server.tool()(tools.get_indexing_status)
    server.tool()(tools.list_property_keys)
    server.tool()(tools.find_page_by_title)
    server.tool()(tools.lookup_path)
    server.tool()(tools.suggest_slug)
    server.tool()(tools.move_page)
    server.tool()(tools.copy_page)
    server.tool()(tools.ensure_path)
    server.tool()(tools.convert_page)
    server.tool()(tools.add_favorite)
    server.tool()(tools.remove_favorite)
    server.tool()(tools.list_favorites)
    server.tool()(tools.pin_page)
    server.tool()(tools.append_to_page)
    server.tool()(tools.update_page_tags)
    server.tool()(tools.update_page_properties)
    server.tool()(tools.sort_pages)
    server.tool()(tools.add_page)
    server.tool()(tools.edit_page)
    server.tool()(tools.delete_page)
    return server
