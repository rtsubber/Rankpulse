"""Page fetcher with SSRF protection, timeout and redirect handling."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import asyncio

HEADERS = {
    "User-Agent": "BoostRank/0.1 (+https://boostrank.co) SEO Audit Bot",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Block internal/private IPs to prevent SSRF
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _is_url_allowed(url: str) -> tuple[bool, str]:
    """Check if a URL is safe to fetch (no SSRF)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"URL scheme not allowed: {scheme}"

    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    if hostname.lower() in BLOCKED_HOSTNAMES:
        return False, f"Hostname '{hostname}' is blocked"

    # Resolve DNS and check the IP
    try:
        ips = socket.getaddrinfo(hostname, None)
        for ip_info in ips:
            ip = ipaddress.ip_address(ip_info[4][0])
            for network in BLOCKED_NETWORKS:
                if ip in network:
                    return False, f"Resolved IP {ip} is in blocked network"
    except socket.gaierror:
        return False, f"Could not resolve hostname: {hostname}"

    return True, "OK"

async def fetch_page(url: str, timeout: int = 15) -> tuple[str, float, str]:
    """
    Fetch a page and return (html, response_time_ms, final_url).
    Follows redirects up to 5 hops. Blocks SSRF targets.
    """
    # SSRF check before fetching
    allowed, reason = _is_url_allowed(url)
    if not allowed:
        raise Exception(f"URL not allowed: {reason}")

    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=5,
        timeout=timeout,
        headers=HEADERS,
    ) as client:
        start = asyncio.get_event_loop().time()
        response = await client.get(url)
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        # Also check the final URL after redirects
        allowed_final, reason_final = _is_url_allowed(str(response.url))
        if not allowed_final:
            raise Exception(f"Redirected to blocked URL: {reason_final}")

        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}")

        # Only process HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise Exception(f"Not an HTML page (content-type: {content_type})")

        return response.text, round(elapsed_ms, 0), str(response.url)