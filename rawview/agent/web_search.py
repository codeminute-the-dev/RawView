"""Read-only web search for the agent (DuckDuckGo instant-answer JSON API; no API key)."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUERY_LEN = 400
_MAX_HTTP_BYTES = 400_000
_FETCH_PAGE_BYTES = 48_000
_HTTP_TIMEOUT_S = 14.0
_USER_AGENT = "RawView/0.1 (reverse-engineering assistant; web search)"


def _host_blocked(hostname: str | None) -> bool:
    if not hostname:
        return True
    h = hostname.lower().strip(".")
    if h in ("localhost", "localhost.localdomain"):
        return True
    if h.endswith(".local") or h.endswith(".internal"):
        return True
    if h in ("0.0.0.0",):
        return True
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return True
    except ValueError:
        pass
    return False


def is_safe_public_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse(url.strip())
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    return not _host_blocked(p.hostname)


def _flatten_related_topics(top: Any, out: list[dict[str, str]], *, depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(top, dict):
        if "Topics" in top and isinstance(top["Topics"], list):
            for t in top["Topics"]:
                _flatten_related_topics(t, out, depth=depth + 1)
            return
        url = str(top.get("FirstURL") or "").strip()
        text = str(top.get("Text") or "").strip()
        if url and is_safe_public_url(url):
            out.append({"title": text[:300] or url, "url": url, "snippet": text[:800]})
    elif isinstance(top, list):
        for item in top:
            _flatten_related_topics(item, out, depth=depth + 1)


def _strip_html_to_text(html: str, max_chars: int) -> str:
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_chars]


def fetch_url_text(url: str, *, max_bytes: int = _FETCH_PAGE_BYTES) -> str:
    if not is_safe_public_url(url):
        return ""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:  # noqa: S310 — validated URL
        raw = resp.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    return raw.decode("utf-8", errors="replace")


def perform_web_search(
    query: str,
    *,
    max_results: int = 6,
    fetch_primary_excerpt: bool = False,
) -> dict[str, Any]:
    q = (query or "").strip()[:_MAX_QUERY_LEN]
    if not q:
        return {"error": "empty_query", "query": query}
    max_results = max(1, min(int(max_results or 6), 12))

    params = urllib.parse.urlencode(
        {"q": q, "format": "json", "no_html": "1", "no_redirect": "1", "t": "rawview"}
    )
    api = "https://api.duckduckgo.com/?" + params
    if not is_safe_public_url(api):
        return {"error": "invalid_search_endpoint"}

    req = urllib.request.Request(api, headers={"User-Agent": _USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:  # noqa: S310
            raw = resp.read(_MAX_HTTP_BYTES)
    except urllib.error.HTTPError as e:
        logger.warning("web_search HTTP error: %s", e)
        return {"error": f"http_{e.code}", "query": q}
    except urllib.error.URLError as e:
        logger.warning("web_search URL error: %s", e)
        return {"error": "network_error", "detail": str(e.reason) if e.reason else str(e), "query": q}
    except OSError as e:
        logger.warning("web_search I/O error: %s", e)
        return {"error": "io_error", "detail": str(e), "query": q}

    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        return {"error": "bad_json", "detail": str(e), "query": q}

    results: list[dict[str, str]] = []
    abs_url = str(data.get("AbstractURL") or "").strip()
    abs_text = str(data.get("AbstractText") or "").strip()
    abs_topic = str(data.get("AbstractSource") or "").strip()
    if abs_url and is_safe_public_url(abs_url):
        title = abs_topic or abs_text[:120] or abs_url
        results.append({"title": title, "url": abs_url, "snippet": abs_text[:1200]})

    for hit in data.get("Results") or []:
        if not isinstance(hit, dict):
            continue
        u = str(hit.get("FirstURL") or "").strip()
        te = str(hit.get("Text") or "").strip()
        if u and is_safe_public_url(u):
            results.append({"title": te[:300] or u, "url": u, "snippet": te[:800]})

    _flatten_related_topics(data.get("RelatedTopics"), results)

    # Dedupe by URL, preserve order
    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for r in results:
        u = r.get("url", "")
        if u in seen:
            continue
        seen.add(u)
        uniq.append(r)
        if len(uniq) >= max_results * 2:
            break
    results = uniq[:max_results]

    primary_url = results[0]["url"] if results else ""
    primary_title = results[0].get("title", "") if results else ""
    primary_snippet = results[0].get("snippet", "") if results else ""

    out: dict[str, Any] = {
        "query": q,
        "primary_url": primary_url,
        "primary_title": primary_title,
        "primary_snippet": primary_snippet,
        "results": results,
        "source": "duckduckgo_instant_answer_api",
        "disclaimer": "Third-party summaries and links; verify before relying on security or legal claims.",
    }

    if fetch_primary_excerpt and primary_url and is_safe_public_url(primary_url):
        try:
            html = fetch_url_text(primary_url)
            out["fetched_excerpt"] = _strip_html_to_text(html, 6000)
            out["fetched_url"] = primary_url
        except Exception as e:
            out["fetch_error"] = str(e)[:500]

    return out
