# SPDX-License-Identifier: MIT

"""Tests for the LeafWiki HTTP client."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from leafwiki_mcp.client import LeafWikiClient, LeafWikiError, Page


def page_data(**overrides: Any) -> dict[str, Any]:
    """Build a representative LeafWiki page response.

    Args:
        **overrides: Page fields that replace the representative defaults.

    Returns:
        JSON-compatible page response data.
    """
    value: dict[str, Any] = {
        "id": "page-1",
        "title": "Page",
        "slug": "page",
        "path": "page",
        "version": "v1",
        "kind": "page",
        "content": "Old",
        "tags": ["one"],
        "properties": {"status": "draft"},
    }
    value.update(overrides)
    return value


def make_client(
    handler: Callable[[httpx.Request], httpx.Response], **kwargs: str
) -> LeafWikiClient:
    """Create a client using an in-memory HTTP transport.

    Args:
        handler: Function that returns responses for captured HTTP requests.
        **kwargs: String arguments forwarded to ``LeafWikiClient``.

    Returns:
        LeafWiki client configured with an HTTPX mock transport.
    """
    return LeafWikiClient(
        "https://wiki.example.test", transport=httpx.MockTransport(handler), **kwargs
    )


def test_authenticate_when_authentication_is_disabled_skips_login() -> None:
    """Authentication-disabled instances should require only the config request."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"authDisabled": True})

    with make_client(handler) as client:
        client.authenticate()

    assert [request.url.path for request in requests] == ["/api/config"]


def test_authenticate_logs_in_with_csrf_token_and_cookies() -> None:
    """Authentication should preserve config cookies and forward its CSRF token."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            return httpx.Response(
                200,
                json={"authDisabled": False},
                headers={"X-CSRF-Token": "csrf-value", "Set-Cookie": "session=value; Path=/"},
            )
        return httpx.Response(200, json={"requiresTotp": False})

    with make_client(handler, username="editor", password="secret") as client:
        client.authenticate()

    login = requests[1]
    assert login.headers["X-CSRF-Token"] == "csrf-value"
    assert login.headers["Cookie"] == "session=value"
    assert login.read() == b'{"identifier":"editor","password":"secret"}'


def test_authenticate_without_credentials_raises_helpful_error() -> None:
    """Required authentication without credentials should fail before login."""
    with (
        make_client(lambda _request: httpx.Response(200, json={"authDisabled": False})) as client,
        pytest.raises(LeafWikiError, match="LEAFWIKI_USERNAME"),
    ):
        client.authenticate()


def test_create_page_with_metadata_creates_then_updates() -> None:
    """Metadata supplied at creation should be applied in a versioned update."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(201, json=page_data())
        return httpx.Response(200, json=page_data(version="v2", content="New", tags=["two"]))

    with make_client(handler) as client:
        result = client.create_page(title="Page", slug="page", content="New", tags=["two"])

    assert result.version == "v2"
    assert requests[0].read() == b'{"title":"Page","slug":"page","kind":"page","parentId":null}'
    assert requests[1].method == "PUT"
    update_body = json.loads(requests[1].read())
    assert update_body["version"] == "v1"
    assert update_body["properties"] == {"status": "draft"}


def test_get_page_by_path_encodes_query() -> None:
    """Path lookup should preserve the slash-separated path as one query value."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=page_data(path="parent/child"))

    with make_client(handler) as client:
        result = client.get_page(path="/parent/child/")

    assert result.path == "parent/child"
    assert seen_request is not None
    assert seen_request.url.params["path"] == "parent/child"


def test_search_pages_sends_repeated_tags_and_pagination() -> None:
    """Search should forward each normalized tag and pagination parameter."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json={"count": 1, "items": [{"page_id": "page-1"}]})

    with make_client(handler) as client:
        result = client.search_pages(
            query="durable memory", tags=["agent", " docs "], offset=20, limit=10
        )

    assert result["count"] == 1
    assert seen_request is not None
    assert seen_request.url.path == "/api/search"
    assert seen_request.url.params.get_list("tags") == ["agent", "docs"]
    assert seen_request.url.params["q"] == "durable memory"
    assert seen_request.url.params["offset"] == "20"
    assert seen_request.url.params["limit"] == "10"


def test_search_pages_requires_query_or_tag() -> None:
    """Empty searches should fail locally instead of issuing an invalid API request."""
    with (
        make_client(lambda _request: httpx.Response(500)) as client,
        pytest.raises(ValueError, match="query or at least one tag"),
    ):
        client.search_pages()


def test_browse_tree_passes_optional_depth() -> None:
    """Tree browsing should forward an explicit depth limit."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json={"id": "root", "children": []})

    with make_client(handler) as client:
        result = client.browse_tree(depth=2)

    assert result["id"] == "root"
    assert seen_request is not None
    assert seen_request.url.params["depth"] == "2"


def test_list_tags_accepts_top_level_array_response() -> None:
    """Tag listing should accept LeafWiki's top-level JSON array response."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=[{"tag": "agent", "count": 3}])

    with make_client(handler) as client:
        result = client.list_tags(query="ag", selected=["docs"], limit=12)

    assert result == [{"tag": "agent", "count": 3}]
    assert seen_request is not None
    assert dict(seen_request.url.params) == {"q": "ag", "limit": "12", "selected": "docs"}


def test_find_pages_by_property_sends_key_and_value() -> None:
    """Property lookup should return the API's page summary array."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=[{"id": "page-1", "path": "decisions/one"}])

    with make_client(handler) as client:
        result = client.find_pages_by_property(key="status", value="approved")

    assert result[0]["id"] == "page-1"
    assert seen_request is not None
    assert dict(seen_request.url.params) == {"key": "status", "value": "approved"}


def test_find_page_by_title_accepts_matches_response_object() -> None:
    """Title lookup should preserve LeafWiki's matches response object."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json={"matches": [{"id": "page-1"}], "count": 1})

    with make_client(handler) as client:
        result = client.find_page_by_title(title="Decision")

    assert result == {"matches": [{"id": "page-1"}], "count": 1}
    assert seen_request is not None
    assert dict(seen_request.url.params) == {"title": "Decision"}


def test_list_favorites_extracts_pages_from_response_object() -> None:
    """Favorite listing should return the pages nested in LeafWiki's response object."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pages": [{"id": "page-1"}]})

    with make_client(handler) as client:
        result = client.list_favorites()

    assert result == [{"id": "page-1"}]


def test_list_favorites_rejects_missing_pages_array() -> None:
    """Favorite listing should reject malformed response objects."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pages": {}})

    with (
        make_client(handler) as client,
        pytest.raises(LeafWikiError, match="favorites without a pages array"),
    ):
        client.list_favorites()


def test_get_page_links_resolves_path_before_requesting_links() -> None:
    """Link lookup by path should first resolve the page ID."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/pages/by-path":
            return httpx.Response(200, json=page_data())
        return httpx.Response(200, json={"backlinks": [], "outgoings": [], "counts": {}})

    with make_client(handler) as client:
        result = client.get_page_links(path="page")

    assert result["backlinks"] == []
    assert [request.url.path for request in requests] == [
        "/api/pages/by-path",
        "/api/pages/page-1/links",
    ]


def test_revision_operations_resolve_page_and_forward_pagination() -> None:
    """Revision operations should resolve selectors and target the revision endpoints."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/pages/page-1":
            return httpx.Response(200, json=page_data())
        if request.url.path.endswith("/revisions"):
            return httpx.Response(200, json={"revisions": [{"id": "rev-1"}], "nextCursor": "next"})
        return httpx.Response(
            200, json={"revision": {"id": "rev-1"}, "content": "Earlier", "assets": []}
        )

    with make_client(handler) as client:
        revisions = client.list_page_revisions(page_id="page-1", cursor="cursor", limit=25)
        snapshot = client.get_page_revision(page_id="page-1", revision_id="rev-1")

    assert revisions["nextCursor"] == "next"
    assert snapshot["content"] == "Earlier"
    assert requests[1].url.path == "/api/pages/page-1/revisions"
    assert dict(requests[1].url.params) == {"cursor": "cursor", "limit": "25"}
    assert requests[3].url.path == "/api/pages/page-1/revisions/rev-1"


def test_delete_page_sends_version_and_recursive_flag() -> None:
    """Deletion should include concurrency and recursive query parameters."""
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(204)

    current = Page.from_dict(page_data())
    with make_client(handler) as client:
        result = client.delete_page(current, recursive=True)

    assert result == {"deleted": True, "id": "page-1", "path": "page"}
    assert seen_request is not None
    assert dict(seen_request.url.params) == {"version": "v1", "recursive": "true"}


def test_api_error_uses_leafwiki_message() -> None:
    """HTTP errors should expose LeafWiki's useful response message."""
    with (
        make_client(
            lambda _request: httpx.Response(409, json={"message": "version conflict"})
        ) as client,
        pytest.raises(LeafWikiError, match="version conflict"),
    ):
        client.get_page(page_id="page-1")
