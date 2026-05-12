"""Page fetcher with timeout and redirect handling."""

import httpx
import asyncio

HEADERS = {
    "User-Agent": "RankPulse/0.1 (+https://rankpulse.co) SEO Audit Bot",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

async def fetch_page(url: str, timeout: int = 15) -> tuple[str, float, str]:
    """
    Fetch a page and return (html, response_time_ms, final_url).
    Follows redirects up to 5 hops.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=5,
        timeout=timeout,
        headers=HEADERS,
    ) as client:
        start = asyncio.get_event_loop().time()
        response = await client.get(url)
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}")

        # Only process HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise Exception(f"Not an HTML page (content-type: {content_type})")

        return response.text, round(elapsed_ms, 0), str(response.url)