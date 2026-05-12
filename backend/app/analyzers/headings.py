"""Heading structure analyzer — H1-H6 hierarchy."""

from bs4 import BeautifulSoup

def analyze_headings(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    issues = []

    heading_tags = ["h1", "h2", "h3", "h4", "h5", "h6"]
    headings = {}

    for tag_name in heading_tags:
        found = soup.find_all(tag_name)
        headings[tag_name] = [h.get_text(strip=True) for h in found]

    h1_count = len(headings["h1"])
    total_count = sum(len(v) for v in headings.values())

    # Build heading structure (ordered)
    structure = []
    for tag_name in heading_tags:
        for h in soup.find_all(tag_name):
            structure.append({
                "level": int(tag_name[1]),
                "tag": tag_name,
                "text": h.get_text(strip=True)[:100],
            })

    # H1 checks
    if h1_count == 0:
        issues.append({
            "severity": "critical",
            "category": "headings",
            "message": "Missing H1 tag",
            "detail": "Every page should have exactly one H1 tag containing the primary keyword.",
            "fix": "Add an H1 tag with your main keyword/topic.",
        })
    elif h1_count > 1:
        issues.append({
            "severity": "warning",
            "category": "headings",
            "message": f"Multiple H1 tags found ({h1_count})",
            "detail": f"H1 tags: {[h[:60] for h in headings['h1']]}",
            "fix": "Use only one H1 per page. Convert extras to H2.",
        })

    # Empty headings
    for tag_name in heading_tags:
        empties = [h for h in headings[tag_name] if not h]
        if empties:
            issues.append({
                "severity": "warning",
                "category": "headings",
                "message": f"Empty {tag_name.upper()} tags found ({len(empties)})",
                "detail": "Empty headings provide no context to search engines.",
                "fix": f"Remove empty {tag_name.upper()} tags or add meaningful text.",
            })

    # Heading hierarchy check
    prev_level = 0
    for item in structure:
        level = item["level"]
        if prev_level > 0 and level > prev_level + 1:
            issues.append({
                "severity": "info",
                "category": "headings",
                "message": f"Skipped heading level: H{prev_level} → H{level}",
                "detail": f'"{structure[max(0, len([s for s in structure[:structure.index(item)]])-1)].get("text","")}" → "{item["text"][:60]}"',
                "fix": f"Maintain proper hierarchy: don't skip from H{prev_level} to H{level}.",
            })
        prev_level = level

    # No headings at all
    if total_count == 0:
        issues.append({
            "severity": "critical",
            "category": "headings",
            "message": "No heading tags found on this page",
            "detail": "Headings help search engines understand page structure.",
            "fix": "Add H1 for the main topic, H2 for sections, H3 for subsections.",
        })

    return {
        "h1_count": h1_count,
        "total_count": total_count,
        "structure": structure,
        "headings": {k: v for k, v in headings.items() if v},
        "issues": issues,
    }