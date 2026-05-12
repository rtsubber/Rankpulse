"""Meta tag analyzer — title, description, OG tags, canonical, robots."""

from bs4 import BeautifulSoup

def analyze_meta_tags(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    issues = []

    # Title tag
    title_tag = soup.find("title")
    title = title_tag.string.strip() if title_tag and title_tag.string else ""
    title_length = len(title)

    if not title:
        issues.append({
            "severity": "critical",
            "category": "meta",
            "message": "Missing <title> tag",
            "detail": "Every page needs a unique, descriptive title tag.",
            "fix": "Add a <title> tag with your primary keyword and brand name.",
        })
    elif title_length < 30:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": f"Title tag is too short ({title_length} chars)",
            "detail": f'Current: "{title}"',
            "fix": "Aim for 50-60 characters. Include your primary keyword.",
        })
    elif title_length > 60:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": f"Title tag is too long ({title_length} chars)",
            "detail": f'Current: "{title[:60]}..." — Google truncates at ~60 chars.',
            "fix": "Shorten to 50-60 characters while keeping keywords.",
        })

    # Meta description
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "").strip() if desc_tag else ""
    description_length = len(description)

    if not description:
        issues.append({
            "severity": "critical",
            "category": "meta",
            "message": "Missing meta description",
            "detail": "Meta descriptions influence click-through rates from search results.",
            "fix": "Write a compelling 150-160 character description with your target keyword.",
        })
    elif description_length < 120:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": f"Meta description is too short ({description_length} chars)",
            "detail": f'Current: "{description[:100]}..."',
            "fix": "Expand to 150-160 characters for better SERP snippets.",
        })
    elif description_length > 160:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": f"Meta description is too long ({description_length} chars)",
            "detail": "Google truncates descriptions at ~160 characters.",
            "fix": "Trim to 150-160 characters while keeping the key message.",
        })

    # Canonical URL
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href", "") if canonical_tag else ""

    if not canonical:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": "Missing canonical URL",
            "detail": "Without a canonical tag, Google may index duplicate URLs.",
            "fix": f'Add <link rel="canonical" href="{url}" />',
        })

    # OG tags (social sharing)
    og_title_tag = soup.find("meta", property="og:title")
    og_desc_tag = soup.find("meta", property="og:description")
    og_image_tag = soup.find("meta", property="og:image")
    og_type_tag = soup.find("meta", property="og:type")

    og_title = og_title_tag.get("content", "") if og_title_tag else ""
    og_image = og_image_tag.get("content", "") if og_image_tag else ""

    if not og_title:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": "Missing og:title tag",
            "detail": "OG tags control how your page appears when shared on Facebook, LinkedIn, etc.",
            "fix": "Add <meta property='og:title' content='Your Page Title' />",
        })

    if not og_image:
        issues.append({
            "severity": "warning",
            "category": "meta",
            "message": "Missing og:image tag",
            "detail": "Pages without og:image show no image preview on social shares.",
            "fix": "Add <meta property='og:image' content='https://example.com/image.jpg' />",
        })

    # Twitter card
    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    if not twitter_card:
        issues.append({
            "severity": "info",
            "category": "meta",
            "message": "Missing Twitter card tags",
            "detail": "Twitter cards improve how links appear in tweets.",
            "fix": "Add <meta name='twitter:card' content='summary_large_image' />",
        })

    # Robots meta
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    if robots_tag:
        robots_content = robots_tag.get("content", "")
        if "noindex" in robots_content.lower():
            issues.append({
                "severity": "critical",
                "category": "meta",
                "message": "Page is set to noindex",
                "detail": f'Robots meta tag: "{robots_content}" — this page will NOT appear in Google.',
                "fix": "Remove 'noindex' from the robots meta tag if you want this page indexed.",
            })

    # Viewport (mobile)
    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    if not viewport_tag:
        issues.append({
            "severity": "critical",
            "category": "meta",
            "message": "Missing viewport meta tag",
            "detail": "Without viewport, your page won't render correctly on mobile devices.",
            "fix": "Add <meta name='viewport' content='width=device-width, initial-scale=1' />",
        })

    return {
        "title": title,
        "title_length": title_length,
        "description": description,
        "description_length": description_length,
        "canonical": canonical,
        "og_title": og_title,
        "og_image": og_image,
        "og_type": og_type_tag.get("content", "") if og_type_tag else "",
        "issues": issues,
    }