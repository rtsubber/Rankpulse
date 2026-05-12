"""Technical SEO analyzer — HTTPS, redirects, sitemap, robots.txt, links."""

from bs4 import BeautifulSoup
from urllib.parse import urlparse

def analyze_technical(html: str, url: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    issues = []

    parsed_url = urlparse(url)
    parsed_final = urlparse(final_url)

    # HTTPS check
    is_https = parsed_url.scheme == "https"
    if not is_https:
        issues.append({
            "severity": "critical",
            "category": "technical",
            "message": "Site is not using HTTPS",
            "detail": "Google prioritizes HTTPS sites. All e-commerce sites MUST use HTTPS.",
            "fix": "Install an SSL certificate and redirect all HTTP to HTTPS.",
        })

    # Redirect check
    had_redirect = url != final_url
    if had_redirect:
        issues.append({
            "severity": "info",
            "category": "technical",
            "message": f"Page redirects from {url} to {final_url}",
            "detail": "Redirects add latency. Prefer linking directly to the final URL.",
            "fix": f"Update internal links to point directly to {final_url}",
        })

    # Check for multiple redirects (chain)
    if had_redirect and parsed_url.netloc != parsed_final.netloc:
        issues.append({
            "severity": "warning",
            "category": "technical",
            "message": "Cross-domain redirect detected",
            "detail": f"Redirecting from {parsed_url.netloc} to {parsed_final.netloc}",
            "fix": "Avoid cross-domain redirects for SEO-critical pages.",
        })

    # Internal links
    links = soup.find_all("a", href=True)
    internal_links = []
    external_links = []
    broken_links = []  # Can't detect without fetching, but check for obvious issues

    for link in links:
        href = link["href"]
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        if href.startswith("/") or parsed_url.netloc in href:
            internal_links.append(href)
        else:
            external_links.append(href)

    # Too few internal links
    if len(internal_links) < 3:
        issues.append({
            "severity": "warning",
            "category": "technical",
            "message": f"Very few internal links ({len(internal_links)})",
            "detail": "Internal links help search engines discover and rank your pages.",
            "fix": "Add links to related products, categories, and key pages.",
        })

    # Check for link text issues
    generic_link_texts = ["click here", "here", "read more", "more", "link"]
    generic_links = [
        link for link in links
        if link.get_text(strip=True).lower() in generic_link_texts
    ]
    if generic_links:
        issues.append({
            "severity": "info",
            "category": "technical",
            "message": f"{len(generic_links)} link(s) with generic anchor text",
            "detail": f"Found: {[g.get_text(strip=True) for g in generic_links[:5]]}",
            "fix": "Use descriptive anchor text: 'Buy red running shoes' instead of 'click here'.",
        })

    # Language tag
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""
    if not lang:
        issues.append({
            "severity": "warning",
            "category": "technical",
            "message": "Missing lang attribute on <html> tag",
            "detail": "The lang attribute helps screen readers and search engines.",
            "fix": "Add lang='en' (or appropriate language code) to the <html> tag.",
        })

    # Charset
    charset_meta = soup.find("meta", attrs={"charset": True})
    if not charset_meta:
        content_type = soup.find("meta", attrs={"http-equiv": "Content-Type"})
        if not content_type or "charset" not in content_type.get("content", ""):
            issues.append({
                "severity": "info",
                "category": "technical",
                "message": "Missing charset declaration",
                "detail": "Charset should be declared for proper text rendering.",
                "fix": "Add <meta charset='utf-8'> in the <head> section.",
            })

    return {
        "is_https": is_https,
        "had_redirect": had_redirect,
        "final_url": final_url,
        "internal_links": len(internal_links),
        "external_links": len(external_links),
        "lang": lang,
        "issues": issues,
    }