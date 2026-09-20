# SPDX-License-Identifier: MIT

"""Tests for the LeafWiki HTTP client."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from leafwiki_mcp.client import (
    LeafWikiClient,
    LeafWikiConnectionError,
    LeafWikiError,
    Page,
)


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


def replace_content(client: LeafWikiClient, page: Page, content: str) -> Page:
    """Send a complete versioned update that changes only a page's content.

    Args:
        client: Client used to perform the update.
        page: Current page supplying the version and preserved fields.
        content: Replacement Markdown content.

    Returns:
        Page returned by LeafWiki for the update.
    """
    return client.update_page(
        page,
        title=page.title,
        slug=page.slug,
        content=content,
        tags=page.tags,
        properties=page.properties,
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


def test_expired_session_reauthenticates_and_replays_read() -> None:
    """A rejected read should log in again and repeat the original request."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": False})
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"requiresTotp": False})
        if sum(item.url.path == "/api/pages/page-1" for item in requests) == 1:
            return httpx.Response(401, json={"message": "session expired"})
        return httpx.Response(200, json=page_data())

    with make_client(handler, username="editor", password="secret") as client:
        page = client.get_page(page_id="page-1")

    assert page.id == "page-1"
    assert [request.url.path for request in requests] == [
        "/api/pages/page-1",
        "/api/config",
        "/api/auth/login",
        "/api/pages/page-1",
    ]


def test_reauthenticated_mutation_replays_with_refreshed_csrf_token() -> None:
    """A replayed mutation should carry the CSRF token issued by the new session."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": False})
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200, json={"requiresTotp": False}, headers={"X-CSRF-Token": "fresh"}
            )
        if request.method == "GET":
            return httpx.Response(200, json=page_data())
        if sum(item.method == "PUT" for item in requests) == 1:
            return httpx.Response(401, json={"message": "session expired"})
        return httpx.Response(200, json=page_data(version="v2", content="New"))

    with make_client(handler, username="editor", password="secret") as client:
        page = client.get_page(page_id="page-1")
        updated = replace_content(client, page, "New")

    updates = [request for request in requests if request.method == "PUT"]
    assert len(updates) == 2
    assert "X-CSRF-Token" not in updates[0].headers
    assert updates[1].headers["X-CSRF-Token"] == "fresh"
    assert json.loads(updates[1].read()) == json.loads(updates[0].read())
    assert updated.version == "v2"


def test_rejected_request_without_credentials_reports_missing_credentials() -> None:
    """A rejection with no credentials configured should name the missing settings."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": False})
        return httpx.Response(401, json={"message": "unauthorized"})

    with make_client(handler) as client, pytest.raises(LeafWikiError) as error:
        client.get_page(page_id="page-1")

    assert "re-authentication failed" in str(error.value)
    assert "LEAFWIKI_USERNAME" in str(error.value)


def test_failed_reauthentication_reports_why_the_login_failed() -> None:
    """Recovery that cannot log in should explain the login failure, not the rejection."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": False})
        if request.url.path == "/api/auth/login":
            return httpx.Response(403, json={"message": "invalid credentials"})
        return httpx.Response(401, json={"message": "session expired"})

    with (
        make_client(handler, username="editor", password="secret") as client,
        pytest.raises(LeafWikiError, match="invalid credentials"),
    ):
        client.get_page(page_id="page-1")


def test_reauthentication_preserves_totp_guidance() -> None:
    """A TOTP account must keep its actionable guidance when recovery runs."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": False})
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"requiresTotp": True})
        return httpx.Response(401, json={"message": "session expired"})

    with (
        make_client(handler, username="editor", password="secret") as client,
        pytest.raises(LeafWikiError, match="requires TOTP"),
    ):
        client.get_page(page_id="page-1")


def test_reauthentication_login_carries_a_token_from_the_new_session() -> None:
    """Recovery must not reuse the CSRF token bound to the rejected session."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            first_config = sum(item.url.path == "/api/config" for item in requests) == 1
            return httpx.Response(
                200,
                json={"authDisabled": False},
                headers={"X-CSRF-Token": "initial" if first_config else "renewed"},
            )
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"requiresTotp": False})
        if sum(item.url.path == "/api/pages/page-1" for item in requests) == 1:
            return httpx.Response(401, json={"message": "session expired"})
        return httpx.Response(200, json=page_data())

    client = make_client(handler, username="editor", password="secret")
    with client:
        client.authenticate()
        client.get_page(page_id="page-1")

    logins = [request for request in requests if request.url.path == "/api/auth/login"]
    assert [login.headers["X-CSRF-Token"] for login in logins] == ["initial", "renewed"]


def test_protocol_failure_is_not_reported_as_unreachable() -> None:
    """A redirect loop is a configuration fault, not a temporarily unreachable host."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TooManyRedirects("too many redirects", request=request)

    with make_client(handler) as client, pytest.raises(LeafWikiError) as error:
        client.get_page(page_id="page-1")

    assert not isinstance(error.value, LeafWikiConnectionError)


def test_dropped_connection_is_retried_for_reads() -> None:
    """A read that loses a pooled connection should be attempted once more."""
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, json=page_data())

    with make_client(handler) as client:
        page = client.get_page(page_id="page-1")

    assert page.id == "page-1"
    assert len(attempts) == 2


def test_ambiguous_transport_failure_is_not_retried_for_mutations() -> None:
    """A mutation that may have been processed must not be repeated."""
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=page_data())
        raise httpx.RemoteProtocolError("Server disconnected", request=request)

    with make_client(handler) as client:
        page = client.get_page(page_id="page-1")
        with pytest.raises(LeafWikiConnectionError, match="Connect to LeafWiki"):
            replace_content(client, page, "New")

    assert sum(request.method == "PUT" for request in attempts) == 1


def test_connection_failure_is_retried_for_mutations() -> None:
    """A mutation that never reached LeafWiki may be attempted once more."""
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=page_data())
        if sum(item.method == "PUT" for item in attempts) == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json=page_data(version="v2", content="New"))

    with make_client(handler) as client:
        page = client.get_page(page_id="page-1")
        updated = replace_content(client, page, "New")

    assert updated.version == "v2"
    assert sum(request.method == "PUT" for request in attempts) == 2


def test_unreachable_instance_raises_a_connection_error() -> None:
    """Exhausted retries should raise the connection-specific error type."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with (
        make_client(handler) as client,
        pytest.raises(LeafWikiConnectionError, match="Connect to LeafWiki"),
    ):
        client.get_page(page_id="page-1")


def test_permission_denial_is_not_treated_as_an_expired_session() -> None:
    """A 403 is an authorization decision, so logging in again must not be attempted."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(403, json={"message": "forbidden"})

    with (
        make_client(handler, username="editor", password="secret") as client,
        pytest.raises(LeafWikiError, match="forbidden"),
    ):
        client.get_page(page_id="page-1")

    assert [request.url.path for request in requests] == ["/api/pages/page-1"]


def test_timeout_is_not_retried() -> None:
    """A request that spent its whole timeout budget should not spend it twice."""
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        raise httpx.ConnectTimeout("timed out", request=request)

    with (
        make_client(handler) as client,
        pytest.raises(LeafWikiConnectionError, match="Connect to LeafWiki"),
    ):
        client.get_page(page_id="page-1")

    assert len(attempts) == 1


def test_rejected_login_is_not_submitted_twice() -> None:
    """Invalid credentials must not be resubmitted, which would consume lockout attempts."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": False})
        return httpx.Response(401, json={"message": "invalid credentials"})

    with (
        make_client(handler, username="editor", password="wrong") as client,
        pytest.raises(LeafWikiError, match="invalid credentials"),
    ):
        client.authenticate()

    assert [request.url.path for request in requests] == ["/api/config", "/api/auth/login"]


def test_refreshed_csrf_token_replays_on_an_authentication_disabled_instance() -> None:
    """A recovered token should be replayed even though no login was required."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            return httpx.Response(
                200, json={"authDisabled": True}, headers={"X-CSRF-Token": "issued"}
            )
        if request.method == "GET":
            return httpx.Response(200, json=page_data())
        if "X-CSRF-Token" not in request.headers:
            return httpx.Response(401, json={"message": "missing CSRF token"})
        return httpx.Response(200, json=page_data(version="v2", content="New"))

    with make_client(handler) as client:
        page = client.get_page(page_id="page-1")
        updated = replace_content(client, page, "New")

    updates = [request for request in requests if request.method == "PUT"]
    assert updated.version == "v2"
    assert len(updates) == 2
    assert updates[1].headers["X-CSRF-Token"] == "issued"


def test_unchanged_csrf_token_is_not_replayed() -> None:
    """A refresh that changes nothing should report the rejection instead of retrying."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"authDisabled": True})
        return httpx.Response(401, json={"message": "unauthorized"})

    with make_client(handler) as client, pytest.raises(LeafWikiError, match="unauthorized"):
        client.get_page(page_id="page-1")

    assert [request.url.path for request in requests] == ["/api/pages/page-1", "/api/config"]
