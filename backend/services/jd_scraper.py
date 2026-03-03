"""JD extraction from a URL using httpx + GPT-4o-mini."""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_MAX_PAGE_CHARS = 12_000  # chars sent to GPT after HTML stripping


def _validate_url(url: str) -> None:
    """Raise ValueError if the URL is unsafe to fetch (SSRF prevention).

    Blocks:
    - Non-http/https schemes (file://, ftp://, etc.)
    - Private/loopback/link-local/reserved IP ranges (RFC 1918, 169.254.x.x, etc.)
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http:// and https:// URLs are supported.")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL — missing hostname.")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname '{hostname}'.")
    for info in infos:
        raw_addr = info[4][0]
        try:
            ip = ipaddress.ip_address(raw_addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError("Access to internal network addresses is not allowed.")


async def scrape_jd_from_url(url: str) -> str:
    """Fetch a job posting URL and return clean JD text.

    Raises:
        ValueError: Page could not be fetched or contained too little text
                    (e.g. JavaScript-rendered SPA), or URL is unsafe.
        RuntimeError: GPT extraction failed.
    """
    _validate_url(url)

    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx package is not installed — cannot scrape URLs.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text
    except httpx.TimeoutException:
        raise ValueError(
            "The URL took too long to load. Please paste the job description manually."
        )
    except httpx.HTTPStatusError as e:
        raise ValueError(
            f"Could not access that URL (HTTP {e.response.status_code}). "
            "Please paste the job description manually."
        )
    except Exception as e:
        raise ValueError(
            f"Could not fetch the URL: {e}. Please paste the job description manually."
        )

    # Strip scripts, styles, then all remaining HTML tags
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < 200:
        raise ValueError(
            "This page contains very little extractable text — it is likely a "
            "JavaScript-rendered app (e.g. LinkedIn, Workday, Greenhouse). "
            "Please paste the job description text manually."
        )

    oai = AsyncOpenAI()
    response = await oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract job description content from raw webpage text. "
                    "Return ONLY the job-related content: job title, team/department, "
                    "key responsibilities, requirements, qualifications, and about-the-company. "
                    "Remove navigation menus, cookie notices, headers, footers, and anything "
                    "unrelated to the role. Preserve the original wording as closely as possible."
                ),
            },
            {
                "role": "user",
                "content": f"Extract the job description from this webpage text:\n\n{text[:_MAX_PAGE_CHARS]}",
            },
        ],
        max_tokens=2_500,
        temperature=0.1,
    )
    extracted = (response.choices[0].message.content or "").strip()
    if not extracted:
        raise RuntimeError("Could not extract a job description from the page content.")
    return extracted
