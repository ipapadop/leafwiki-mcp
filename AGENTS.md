<!-- SPDX-License-Identifier: MIT -->

# AGENTS.md

## Project overview

This repository implements a Python MCP server for a LeafWiki instance. It exposes
LeafWiki page discovery, organization, revision, favorite, and mutation operations as
MCP tools over stdio. The package uses a `src` layout and requires Python 3.12 or newer.

The canonical repository is `https://github.com/ipapadop/leafwiki-mcp`, the default
branch is `main`, and the conventional remote name is `origin`.

Keep changes focused on this integration. Consult `README.md` for user-facing setup and
the current tool inventory; update it when configuration, commands, or exposed tools
change.

## Setup and commands

Use `uv` for dependency management and command execution:

```bash
uv sync
uv run leafwiki-mcp
```

These commands set up and run a source checkout. Do not describe the project as
installable from PyPI unless a published distribution and its installation workflow
have been verified.

Canonical quality checks are:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

The repository does not currently define GitHub Actions workflows. Until CI is added,
the local commands above are the canonical quality gate and must not be represented as
automatically enforced by GitHub.

During development, run the narrowest relevant test first, for example:

```bash
uv run pytest tests/test_client.py -q
uv run pytest tests/test_server.py -q
uv run pytest tests/test_client.py::test_get_page_by_path_encodes_query -q
```

Do not assume a live LeafWiki instance is available for tests. To exercise the server
manually, configure `LEAFWIKI_URL`, `LEAFWIKI_USERNAME`, and `LEAFWIKI_PASSWORD` as
described in `README.md`. Authentication-disabled instances need only the URL.

## Architecture and boundaries

- `src/leafwiki_mcp/client.py` is the LeafWiki HTTP/API boundary. It owns URL
  normalization, the cookie-preserving HTTPX session, authentication, CSRF handling,
  request encoding, response validation, API error translation, and page models.
- `src/leafwiki_mcp/server.py` is the MCP adaptation layer. `LeafWikiTools` should
  remain a collection of typed, synchronous operations that delegate API behavior to
  `LeafWikiClient`. `create_server()` explicitly registers the public tools.
- `src/leafwiki_mcp/__main__.py` owns CLI parsing, `LEAFWIKI_*` environment defaults,
  client lifetime, authentication, and starting FastMCP with `transport="stdio"`.
- `tests/test_client.py` verifies HTTP contracts with `httpx.MockTransport`, including
  methods, paths, query parameters, headers, cookies, bodies, parsing, and failures.
- `tests/test_server.py` verifies that MCP-facing operations preserve semantics while
  delegating to a mocked `LeafWikiClient`.

Keep these boundaries intact. Do not duplicate HTTP behavior in MCP tool methods or
put MCP registration concerns into the HTTP client.

## Python conventions

- Follow the Ruff and Pyright configuration in `pyproject.toml`. The project uses
  strict type checking, a 100-character line length, double quotes, Google-style
  docstrings, and Ruff-managed import ordering.
- Add type annotations to new functions and meaningful local data structures. Avoid
  broad `Any` where a stable type can be expressed; isolate unavoidable dynamic JSON
  handling at the API boundary.
- Prefer small methods with one responsibility and existing dataclass/model patterns.
  Raise `ValueError` for invalid caller input and `LeafWikiError` for LeafWiki,
  transport, or response-contract failures.
- Public MCP methods need concise, behavior-oriented docstrings. FastMCP exposes these
  descriptions to clients, so document defaults, selector behavior, important
  prerequisites, and destructive effects accurately.
- MCP inputs and outputs must remain JSON/MCP-serializable. Convert `Page` objects with
  `to_dict()` and avoid leaking HTTPX objects, exceptions, dataclasses, or other
  process-local values through tool results.
- Add dependencies only when the standard library and current packages cannot solve
  the problem cleanly. Update both `pyproject.toml` and `uv.lock` intentionally when a
  dependency change is required.

## LeafWiki client rules

- Normalize and validate base URLs. Only HTTP and HTTPS URLs with a host are valid;
  avoid constructing API URLs through unchecked string concatenation.
- Preserve the `httpx.Client` session so authentication cookies and CSRF state survive
  across requests. Close clients through their context manager or `close()`.
- Authentication starts with `GET /api/config`. Skip login when `authDisabled` is
  true. When authentication is required, missing credentials must produce an
  actionable `LeafWikiError`. TOTP accounts are unsupported; retain the guidance to
  use a dedicated editor account without TOTP.
- Forward the most recent `X-CSRF-Token` on non-GET/non-HEAD requests. Do not weaken
  cookie, CSRF, redirect, timeout, or URL-validation behavior without tests that
  demonstrate the intended LeafWiki contract.
- Apply ID-or-path selection consistently. Normalize surrounding whitespace and path
  slashes, prefer a non-empty ID when both selectors are supplied, URL-encode path
  components correctly, and reject calls where neither selector is provided.
- Validate response shapes before returning them. Preserve the response-size limit,
  handle empty bodies where valid, and translate HTTP status, transport, invalid JSON,
  and unexpected JSON-shape failures into useful `LeafWikiError` messages.
- Do not expose credentials, cookies, CSRF tokens, authorization data, or full
  sensitive response bodies in errors or logs.

## MCP tool rules

- Keep tools thin. Argument forwarding, selector resolution, and conversion to
  serializable results belong in `LeafWikiTools`; HTTP endpoint details belong in
  `LeafWikiClient`.
- Use explicit typed parameters with stable defaults. Preserve compatibility when
  changing existing tool names or schemas; MCP clients may depend on them.
- Register every intended public operation explicitly in `create_server()`. Add or
  remove registration tests or assertions when tool exposure changes.
- Keep the tool inventory in `README.md` synchronized with the explicit registrations
  in `create_server()`. Compare the two whenever a tool is added, removed, or renamed.
- Keep the runtime synchronous unless a deliberate repository-wide design change is
  approved. The current client and FastMCP tool methods are synchronous.
- Preserve stdio transport. Never write ordinary diagnostics, progress messages, or
  debug output to stdout because that can corrupt the MCP protocol stream. If runtime
  logging is added, direct it to stderr and avoid sensitive values.
- Features that LeafWiki may disable, such as revisions, should report the server/API
  result clearly rather than being silently emulated by the MCP layer.

## Mutation safety and optimistic concurrency

- Treat page creation, edits, moves, conversions, sorting, metadata replacement, and
  deletion as state-changing operations. Verify request methods, identifiers, parent
  IDs, ordering, and payloads in tests.
- Preserve optimistic concurrency. Updates and deletions use the current page version;
  never discard or fabricate versions to bypass conflicts. Surface LeafWiki conflict
  responses as errors so clients can re-read state and retry deliberately.
- Partial MCP edits must preserve omitted fields. Fetch the current page before an
  edit, substitute existing values for omitted arguments, and send a complete
  versioned update. Distinguish an omitted value from an explicitly empty string,
  empty list, or empty mapping.
- Deletion must resolve the current page first and pass its current version to the API.
  Keep `recursive=False` as the safe default. Do not enable recursive deletion
  implicitly or retry a destructive request after an ambiguous transport failure.
- Creation with optional content or metadata is a create followed by a versioned
  update. Account for the possibility that creation succeeds and the follow-up update
  fails; do not claim the entire operation was rolled back.
- For destructive or broad operations, keep tool descriptions explicit enough that an
  MCP client can ask for confirmation or communicate impact before invocation.

## Testing

- Every behavior change needs a focused regression test. Test the public boundary
  where the contract lives: HTTP behavior in `test_client.py`, delegation and
  MCP-facing semantics in `test_server.py`.
- Use `httpx.MockTransport` for deterministic client tests. Capture requests and assert
  exact HTTP methods, paths, parameters, headers, cookies, and JSON bodies when those
  details are part of the contract.
- Use `Mock(spec=LeafWikiClient)` for tool-layer tests so tests fail when code delegates
  to nonexistent client methods. Assert exact calls, especially for selectors,
  versions, omitted fields, and recursive/destructive flags.
- Cover successful responses and relevant failures: authentication requirements,
  TOTP rejection, validation, non-2xx responses, conflicts, transport errors, invalid
  JSON, incorrect response shapes, and response-size enforcement.
- Tests must not depend on external network access, real credentials, wall-clock
  timing, or mutable LeafWiki data.
- Run the focused test while iterating, then run the full Ruff lint, Ruff format,
  Pyright, and Pytest commands before declaring implementation work complete. A
  documentation-only change may use content inspection instead of rerunning code
  checks when the existing baseline is already known.

## Security and repository hygiene

- Never commit real LeafWiki URLs containing private information, usernames,
  passwords, cookies, tokens, or captured authenticated requests. Use clearly fake
  `.test` values in tests and placeholders in documentation.
- Do not add secrets to command examples, fixtures, snapshots, exception messages, or
  debug logs. Be especially careful when asserting login requests in tests.
- Generated and local artifacts such as `.venv/`, coverage files, caches, `dist/`,
  `htmlcov/`, egg metadata, and bytecode are ignored; do not deliberately add them.
- The project is licensed under MIT. Preserve `LICENSE` and the existing
  `SPDX-License-Identifier: MIT` headers. Add the appropriate comment-form SPDX header
  to new source, configuration, test, and substantial documentation files.
- Preserve unrelated user changes. Avoid broad formatting rewrites, dependency
  upgrades, lockfile churn, or generated artifact changes unless they are required by
  the task.
- Keep `README.md` user-facing. Put durable coding-agent instructions here, and avoid
  maintaining competing copies of the same command or tool inventory.

## Git and GitHub workflow

- Inspect `git status`, the current branch, and relevant diffs before editing. Preserve
  unrelated staged, unstaged, and untracked user work.
- Keep commits focused on the requested change. Do not rewrite existing history,
  force-push, or use destructive Git commands unless explicitly requested.
- Do not push branches, tags, commits, or open pull requests unless the user explicitly
  asks for that external action. Preparing or committing work locally is not permission
  to publish it.
- Use `main` as the default base branch unless repository state or the user identifies
  another base. Use the configured `origin` remote for this repository; do not replace
  or add remotes without checking the existing configuration and request scope.

## Packaging and releases

- The version is defined in `pyproject.toml`. Change it only as part of an intentional
  release or an explicitly requested version update, and keep user-facing version or
  status text synchronized.
- When packaging configuration, release metadata, package contents, or distribution
  behavior changes, run `uv build`. Inspect both the wheel and source distribution to
  confirm that required source, README, license, and metadata are present and that
  local or generated artifacts are absent.
- Do not claim a PyPI release, GitHub release, tag, or automated release workflow exists
  without verifying it. Publishing packages, creating releases, and pushing tags are
  external actions that require explicit user authorization.
- README installation instructions must distinguish source-checkout setup from a
  published-package installation. Keep prerequisites, repository clone commands,
  configuration and credential safety, operational limitations, troubleshooting,
  development checks, project links, and licensing accurate.

## Definition of done

Before handing off a change:

1. Confirm the change is scoped to the requested behavior and respects module
   boundaries.
2. Add or update focused tests for every changed contract.
3. Run the relevant focused tests, followed by Ruff lint, Ruff format, Pyright, and the
   complete Pytest suite for code changes.
4. Update `README.md` when setup, configuration, exposed tools, or user-visible
   behavior changes. Compare its tool inventory directly with the registrations in
   `create_server()`.
5. Review the final diff for accidental secrets, generated files, unrelated edits,
   unsafe destructive defaults, and protocol output on stdout.
6. For packaging or release metadata changes, build and inspect both distributions.
7. Report the commands run and their actual results; do not claim checks passed unless
   they were executed successfully.
