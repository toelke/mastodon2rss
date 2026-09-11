"""Guard the Python version pin in the Dockerfile.

Mastodon.py looks up type hints once per attribute assignment while parsing API
responses, which makes parsing a home timeline take seconds instead of
milliseconds:

    https://github.com/halcy/Mastodon.py/issues/448

We render the timeline synchronously in /feed, so that cost lands directly in
the response time. On our (slow) deployment host the parse alone is roughly:

    python 3.13   ~13s
    python 3.14   ~22s

and the reverse proxy in front of us gives up after 15s. Python 3.14 evaluates
annotations lazily (PEP 649/749), which makes each lookup about twice as
expensive, so it is the version that pushes us over the limit.

This test fails the build if someone (renovate, usually) moves the base image to
3.14 while that upstream bug is still present. It does NOT measure wall time --
CI runners are too variable for that. Instead it counts how often Mastodon.py
reaches typing.get_type_hints while parsing a handful of statuses: with the bug
that is ~1400 calls, once upstream memoises it, ~3. So once the bug is fixed
this test goes green on any version and the pin can be dropped.

No Mastodon server is needed: the slow part is parsing a response, not fetching
one.
"""

import sys
import time
import typing

# Wrap typing.get_type_hints before Mastodon.py binds it with "from typing
# import get_type_hints", so we count calls that actually reach it. If upstream
# adds a cache of its own, the calls stop arriving here and the count collapses.
_calls = 0
_original_get_type_hints = typing.get_type_hints


def _counting_get_type_hints(*args, **kwargs):
    global _calls
    _calls += 1
    return _original_get_type_hints(*args, **kwargs)


typing.get_type_hints = _counting_get_type_hints

from mastodon.return_types import NonPaginatableList, Status  # noqa: E402
from mastodon.types_base import try_cast_recurse  # noqa: E402

# A call count this high can only come from re-deriving hints per attribute.
# The fixed version needs one lookup per distinct entity class (~3 here).
CALL_BUDGET = 100
STATUS_COUNT = 5


def _account(i):
    return {
        "id": str(i), "username": f"u{i}", "acct": f"u{i}", "display_name": f"User {i}",
        "avatar": "https://example.com/a.png", "header": "https://example.com/h.png",
        "url": "https://example.com/@u", "created_at": "2026-01-01T00:00:00.000Z",
        "note": "<p>bio</p>", "emojis": [], "fields": [],
    }


def _status(i, reblog=None):
    return {
        "id": str(i), "uri": "https://example.com/s/1", "url": "https://example.com/s/1",
        "account": _account(i), "content": "<p>hello</p>", "spoiler_text": "",
        "created_at": "2026-09-11T07:00:00.000Z", "visibility": "public",
        "media_attachments": [], "mentions": [], "tags": [], "emojis": [],
        "card": None, "poll": None, "reblog": reblog,
    }


def main():
    global _calls

    # Shaped like a page of /api/v1/timelines/home: statuses wrapping boosts.
    payload = [_status(i, reblog=_status(1000 + i)) for i in range(STATUS_COUNT)]

    _calls = 0
    started = time.perf_counter()
    try_cast_recurse(NonPaginatableList[Status], payload)
    elapsed = time.perf_counter() - started

    version = ".".join(str(p) for p in sys.version_info[:3])
    print(f"python {version}: parsed {STATUS_COUNT} statuses in {elapsed:.2f}s, "
          f"{_calls} get_type_hints call(s)")

    if _calls <= CALL_BUDGET:
        print("Mastodon.py no longer re-derives type hints per attribute -- "
              "upstream issue 448 looks fixed, the Dockerfile pin to python 3.13 "
              "can be dropped.")
        return 0

    if sys.version_info >= (3, 14):
        print(
            f"FAIL: running on python {version} while Mastodon.py still derives type "
            f"hints per attribute ({_calls} calls for {STATUS_COUNT} statuses).\n"
            "      This makes /feed exceed the 15s proxy timeout in production.\n"
            "      Keep the Dockerfile on python 3.13 until "
            "https://github.com/halcy/Mastodon.py/issues/448 is fixed.",
            file=sys.stderr,
        )
        return 1

    print("Known-slow Mastodon.py, but python < 3.14 keeps /feed within the timeout.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
