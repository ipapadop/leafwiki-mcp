# SPDX-License-Identifier: MIT

"""HTTP client for the LeafWiki API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Self, cast
from urllib.parse import quote

import httpx

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
type JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class LeafWikiError(RuntimeError):
    """An error returned while communicating with LeafWiki."""


@dataclass(frozen=True, slots=True)
class Page:
    """A LeafWiki page returned by the API."""

    id: str
    title: str
    slug: str
    path: str
    version: str
    kind: str
    content: str
    tags: list[str]
    properties: dict[str, str]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Page:
        """Create a page from a LeafWiki API response."""
        try:
            raw_tags = value.get("tags")
            tags = (
                [str(tag) for tag in cast("list[Any]", raw_tags)]
                if isinstance(raw_tags, list)
                else []
            )
            raw_properties = value.get("properties")
            properties = (
                {
                    str(key): str(item)
                    for key, item in cast("dict[Any, Any]", raw_properties).items()
                }
                if isinstance(raw_properties, dict)
                else {}
            )
            return cls(
                id=str(value["id"]),
                title=str(value["title"]),
                slug=str(value["slug"]),
                path=str(value["path"]),
                version=str(value["version"]),
                kind=str(value["kind"]),
                content=str(value.get("content", "")),
                tags=tags,
                properties=properties,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise LeafWikiError(f"Invalid page returned by LeafWiki: {error}") from error

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of the page."""
        return asdict(self)


class LeafWikiClient:
    """Client for page mutations through the LeafWiki HTTP API."""

    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the client and its cookie-preserving HTTP session."""
        normalized_url = base_url.strip().rstrip("/")
        parsed_url = httpx.URL(normalized_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.host:
            raise ValueError(f"Invalid LeafWiki URL {base_url!r}")

        self._username = username
        self._password = password
        self._csrf_token = ""
        self._client = httpx.Client(
            base_url=normalized_url,
            follow_redirects=True,
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> Self:
        """Return this client as a context manager."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Close the underlying HTTP session."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._client.close()

    def authenticate(self) -> None:
        """Connect to LeafWiki and authenticate when required."""
        config = self._object_request("GET", "/api/config")
        if bool(config.get("authDisabled")):
            return
        if not self._username or not self._password:
            raise LeafWikiError(
                "LeafWiki requires authentication; set LEAFWIKI_USERNAME and LEAFWIKI_PASSWORD"
            )

        result = self._object_request(
            "POST",
            "/api/auth/login",
            json={"identifier": self._username, "password": self._password},
        )
        if bool(result.get("requiresTotp")):
            raise LeafWikiError(
                "LeafWiki account requires TOTP; use a dedicated editor account without TOTP "
                "for MCP"
            )

    def create_page(
        self,
        *,
        title: str,
        slug: str,
        parent_id: str = "",
        kind: str = "page",
        content: str | None = None,
        tags: list[str] | None = None,
        properties: dict[str, str] | None = None,
    ) -> Page:
        """Create a page or section, then apply optional content and metadata."""
        if not title or not slug:
            raise ValueError("title and slug are required")
        if kind not in {"page", "section"}:
            raise ValueError("kind must be page or section")

        created = self._page_request(
            "POST",
            "/api/pages",
            json={
                "title": title,
                "slug": slug,
                "kind": kind,
                "parentId": None if parent_id in {"", "root"} else parent_id,
            },
        )
        if content is None and tags is None and properties is None:
            return created
        return self.update_page(
            created,
            title=created.title,
            slug=created.slug,
            content=created.content if content is None else content,
            tags=created.tags if tags is None else tags,
            properties=created.properties if properties is None else properties,
        )

    def get_page(self, *, page_id: str = "", path: str = "") -> Page:
        """Retrieve a page by ID or slash-separated path."""
        normalized_id = page_id.strip()
        normalized_path = path.strip().strip("/")
        if normalized_id:
            return self._page_request("GET", f"/api/pages/{quote(normalized_id, safe='')}")
        if normalized_path:
            return self._page_request("GET", "/api/pages/by-path", params={"path": normalized_path})
        raise ValueError("one of id or path is required")

    def search_pages(
        self,
        *,
        query: str = "",
        tags: list[str] | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search page content and metadata, optionally filtering by tags."""
        normalized_tags = [tag.strip() for tag in tags or [] if tag.strip()]
        if not query.strip() and not normalized_tags:
            raise ValueError("query or at least one tag is required")
        params: list[tuple[str, str | int]] = [("q", query), ("offset", offset), ("limit", limit)]
        params.extend(("tags", tag) for tag in normalized_tags)
        return self._object_request("GET", "/api/search", params=params)

    def browse_tree(self, *, depth: int | None = None) -> dict[str, Any]:
        """Retrieve the LeafWiki page tree, optionally limited to a depth."""
        params = None if depth is None else {"depth": depth}
        return self._object_request("GET", "/api/tree", params=params)

    def get_page_links(self, *, page_id: str = "", path: str = "") -> dict[str, Any]:
        """Retrieve backlinks, outgoing links, and broken links for a page."""
        current = self.get_page(page_id=page_id, path=path)
        return self._object_request("GET", f"/api/pages/{quote(current.id, safe='')}/links")

    def list_tags(
        self,
        *,
        query: str = "",
        selected: list[str] | None = None,
        limit: int = 50,
    ) -> list[Any]:
        """List tags and their usage counts, optionally filtering by name."""
        params: list[tuple[str, str | int]] = [("q", query), ("limit", limit)]
        params.extend(("selected", tag) for tag in selected or [])
        return self._list_request("GET", "/api/tags", params=params)

    def find_pages_by_property(self, *, key: str, value: str = "") -> list[Any]:
        """Find pages carrying a property key and optional value."""
        if not key.strip():
            raise ValueError("property key is required")
        return self._list_request(
            "GET", "/api/properties/pages", params={"key": key, "value": value}
        )

    def list_page_revisions(
        self,
        *,
        page_id: str = "",
        path: str = "",
        cursor: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        """List a page's revision metadata using cursor pagination."""
        current = self.get_page(page_id=page_id, path=path)
        return self._object_request(
            "GET",
            f"/api/pages/{quote(current.id, safe='')}/revisions",
            params={"cursor": cursor, "limit": limit},
        )

    def get_page_revision(
        self,
        *,
        revision_id: str,
        page_id: str = "",
        path: str = "",
    ) -> dict[str, Any]:
        """Retrieve a historical page snapshot, including its content and asset metadata."""
        if not revision_id.strip():
            raise ValueError("revision id is required")
        current = self.get_page(page_id=page_id, path=path)
        return self._object_request(
            "GET",
            f"/api/pages/{quote(current.id, safe='')}/revisions/"
            f"{quote(revision_id.strip(), safe='')}",
        )

    def compare_page_revisions(
        self,
        *,
        page_id: str = "",
        path: str = "",
        base_revision_id: str,
        target_revision_id: str,
    ) -> dict[str, Any]:
        """Compare two historical snapshots of a page."""
        current = self.get_page(page_id=page_id, path=path)
        return self._object_request(
            "GET",
            f"/api/pages/{quote(current.id, safe='')}/revisions/compare",
            params={"base": base_revision_id, "target": target_revision_id},
        )

    def get_indexing_status(self) -> dict[str, Any]:
        """Return the current full-text search indexing status."""
        return self._object_request("GET", "/api/search/status")

    def list_property_keys(self, *, query: str = "", limit: int = 50) -> list[Any]:
        """List available property keys."""
        return self._list_request("GET", "/api/properties", params={"q": query, "limit": limit})

    def find_page_by_title(self, *, title: str) -> dict[str, Any]:
        """Find pages with a matching title."""
        if not title.strip():
            raise ValueError("title is required")
        return self._object_request("GET", "/api/pages/by-title", params={"title": title})

    def lookup_path(self, *, path: str) -> dict[str, Any]:
        """Resolve a path into existing and missing tree segments."""
        if not path.strip():
            raise ValueError("path is required")
        return self._object_request(
            "GET", "/api/pages/lookup", params={"path": path.strip().strip("/")}
        )

    def suggest_slug(
        self, *, title: str, parent_id: str = "", current_id: str = ""
    ) -> dict[str, Any]:
        """Suggest an available slug for a title."""
        if not title.strip():
            raise ValueError("title is required")
        return self._object_request(
            "GET",
            "/api/pages/slug-suggestion",
            params={"title": title, "parentId": parent_id, "currentId": current_id},
        )

    def move_page(
        self,
        *,
        page_id: str = "",
        path: str = "",
        parent_id: str = "",
        position: int | None = None,
    ) -> dict[str, Any]:
        """Move a page under a new parent using its current version."""
        current = self.get_page(page_id=page_id, path=path)
        payload: dict[str, Any] = {"version": current.version, "parentId": parent_id}
        if position is not None:
            payload["position"] = position
        self._json_request("PUT", f"/api/pages/{quote(current.id, safe='')}/move", json=payload)
        return {"moved": True, "id": current.id, "parent_id": parent_id, "position": position}

    def copy_page(
        self,
        *,
        page_id: str = "",
        path: str = "",
        title: str,
        slug: str,
        target_parent_id: str = "",
    ) -> Page:
        """Copy a page and its assets under a new title and slug."""
        current = self.get_page(page_id=page_id, path=path)
        return self._page_request(
            "POST",
            f"/api/pages/copy/{quote(current.id, safe='')}",
            json={
                "targetParentId": None if target_parent_id in {"", "root"} else target_parent_id,
                "title": title,
                "slug": slug,
            },
        )

    def ensure_path(self, *, path: str, title: str, kind: str = "page") -> Page:
        """Ensure a nested path exists, creating missing sections as needed."""
        if kind not in {"page", "section"}:
            raise ValueError("kind must be page or section")
        return self._page_request(
            "POST", "/api/pages/ensure", json={"path": path, "title": title, "kind": kind}
        )

    def convert_page(
        self, *, page_id: str = "", path: str = "", target_kind: str
    ) -> dict[str, Any]:
        """Convert a page to a section or a section to a page."""
        if target_kind not in {"page", "section"}:
            raise ValueError("target kind must be page or section")
        current = self.get_page(page_id=page_id, path=path)
        self._json_request(
            "POST",
            f"/api/pages/convert/{quote(current.id, safe='')}",
            json={"targetKind": target_kind, "version": current.version},
        )
        return {"converted": True, "id": current.id, "target_kind": target_kind}

    def add_favorite(self, *, page_id: str = "", path: str = "") -> dict[str, Any]:
        """Add a page to the authenticated user's favorites."""
        current = self.get_page(page_id=page_id, path=path)
        self._json_request("PUT", f"/api/pages/{quote(current.id, safe='')}/favorite")
        return {"favorited": True, "id": current.id, "path": current.path}

    def remove_favorite(self, *, page_id: str = "", path: str = "") -> dict[str, Any]:
        """Remove a page from the authenticated user's favorites."""
        current = self.get_page(page_id=page_id, path=path)
        self._json_request("DELETE", f"/api/pages/{quote(current.id, safe='')}/favorite")
        return {"favorited": False, "id": current.id, "path": current.path}

    def list_favorites(self) -> list[Any]:
        """List the authenticated user's favorite pages."""
        result = self._object_request("GET", "/api/favorites")
        pages = result.get("pages")
        if not isinstance(pages, list):
            message = "LeafWiki returned favorites without a pages array"
            raise LeafWikiError(message)
        return cast("list[Any]", pages)

    def pin_page(self, *, page_id: str = "", path: str = "", pinned: bool = True) -> Page:
        """Pin or unpin a page using its current version."""
        current = self.get_page(page_id=page_id, path=path)
        return self._page_request(
            "PUT",
            f"/api/pages/{quote(current.id, safe='')}/pin",
            json={"version": current.version, "pinned": pinned},
        )

    def append_to_page(self, *, page_id: str = "", path: str = "", content: str) -> Page:
        """Append Markdown content to a page using its current version."""
        current = self.get_page(page_id=page_id, path=path)
        separator = "\n" if current.content and not current.content.endswith("\n") else ""
        return self.update_page(
            current,
            title=current.title,
            slug=current.slug,
            content=f"{current.content}{separator}{content}",
            tags=current.tags,
            properties=current.properties,
        )

    def update_page_tags(self, *, page_id: str = "", path: str = "", tags: list[str]) -> Page:
        """Replace a page's tags while preserving all other fields."""
        current = self.get_page(page_id=page_id, path=path)
        return self.update_page(
            current,
            title=current.title,
            slug=current.slug,
            content=current.content,
            tags=tags,
            properties=current.properties,
        )

    def update_page_properties(
        self, *, page_id: str = "", path: str = "", properties: dict[str, str]
    ) -> Page:
        """Replace a page's properties while preserving all other fields."""
        current = self.get_page(page_id=page_id, path=path)
        return self.update_page(
            current,
            title=current.title,
            slug=current.slug,
            content=current.content,
            tags=current.tags,
            properties=properties,
        )

    def sort_pages(self, *, parent_id: str, ordered_ids: list[str]) -> dict[str, Any]:
        """Set the child ordering under a parent page."""
        self._json_request(
            "PUT",
            f"/api/pages/{quote(parent_id or 'root', safe='')}/sort",
            json={"orderedIds": ordered_ids},
        )
        return {"sorted": True, "parent_id": parent_id or "root", "ordered_ids": ordered_ids}

    def update_page(
        self,
        current: Page,
        *,
        title: str,
        slug: str,
        content: str,
        tags: list[str],
        properties: dict[str, str],
    ) -> Page:
        """Update a page using its current version for optimistic concurrency."""
        return self._page_request(
            "PUT",
            f"/api/pages/{quote(current.id, safe='')}",
            json={
                "version": current.version,
                "title": title,
                "slug": slug,
                "content": content,
                "tags": tags,
                "properties": properties,
            },
        )

    def delete_page(self, current: Page, *, recursive: bool = False) -> dict[str, str | bool]:
        """Delete a page using its current version."""
        self._json_request(
            "DELETE",
            f"/api/pages/{quote(current.id, safe='')}",
            params={"version": current.version, "recursive": str(recursive).lower()},
        )
        return {"deleted": True, "id": current.id, "path": current.path}

    def _page_request(self, method: str, path: str, **kwargs: Any) -> Page:
        value = self._object_request(method, path, **kwargs)
        return Page.from_dict(value)

    def _object_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        value = self._json_request(method, path, **kwargs)
        if not isinstance(value, dict):
            raise LeafWikiError("LeafWiki returned a non-object JSON response")
        return value

    def _list_request(self, method: str, path: str, **kwargs: Any) -> list[Any]:
        value = self._json_request(method, path, **kwargs)
        if not isinstance(value, list):
            raise LeafWikiError("LeafWiki returned a non-array JSON response")
        return value

    def _json_request(self, method: str, path: str, **kwargs: Any) -> JSONValue:
        headers = dict(kwargs.pop("headers", {}))
        if method not in {"GET", "HEAD"} and self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            message = self._error_message(error.response)
            raise LeafWikiError(
                f"LeafWiki API {method} {path} returned {error.response.status_code}: {message}"
            ) from error
        except httpx.HTTPError as error:
            raise LeafWikiError(f"Connect to LeafWiki: {error}") from error

        if token := response.headers.get("X-CSRF-Token"):
            self._csrf_token = token
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise LeafWikiError(f"LeafWiki response exceeds {MAX_RESPONSE_BYTES} bytes")
        if not response.content.strip():
            return None
        try:
            return cast("JSONValue", response.json())
        except ValueError as error:
            raise LeafWikiError("LeafWiki returned invalid JSON") from error

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            value: object = response.json()
            if isinstance(value, dict):
                response_object = cast("dict[str, Any]", value)
                message_value: object = response_object.get("message") or response_object.get(
                    "error"
                )
                if message_value:
                    return str(message_value).strip()
        except ValueError:
            pass
        return response.text.strip()
