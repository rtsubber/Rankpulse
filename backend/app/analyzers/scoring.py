"""SEO scoring engine — combines all analyzer results into a 0-100 score."""

def calculate_seo_score(meta: dict, headings: dict, images: dict,
                       technical: dict, schema: dict) -> dict:
    """
    Calculate SEO score (0-100) broken down by category.
    Weights: meta 30%, headings 15%, images 20%, technical 20%, schema 15%
    """
    scores = {}

    # --- Meta Tags (30%) ---
    meta_score = 100
    if not meta.get("title"):
        meta_score -= 30
    else:
        tl = meta.get("title_length", 0)
        if tl < 30:
            meta_score -= 15
        elif tl > 60:
            meta_score -= 10

    if not meta.get("description"):
        meta_score -= 25
    else:
        dl = meta.get("description_length", 0)
        if dl < 120:
            meta_score -= 10
        elif dl > 160:
            meta_score -= 10

    if not meta.get("canonical"):
        meta_score -= 10
    if not meta.get("og_title"):
        meta_score -= 10
    if not meta.get("og_image"):
        meta_score -= 10

    scores["meta"] = max(0, meta_score)

    # --- Headings (15%) ---
    heading_score = 100
    h1 = headings.get("h1_count", 0)
    if h1 == 0:
        heading_score -= 50
    elif h1 > 1:
        heading_score -= 20

    if headings.get("total_count", 0) < 3:
        heading_score -= 20

    scores["headings"] = max(0, heading_score)

    # --- Images (20%) ---
    image_score = 100
    total = images.get("total", 0)
    if total == 0:
        image_score -= 30  # No images isn't always bad
    else:
        missing_pct = images.get("missing_alt", 0) / total * 100
        if missing_pct > 50:
            image_score -= 40
        elif missing_pct > 0:
            image_score -= 20

        if images.get("bad_filenames", 0) > 0:
            image_score -= 10

    scores["images"] = max(0, image_score)

    # --- Technical (20%) ---
    tech_score = 100
    if not technical.get("is_https"):
        tech_score -= 40

    if technical.get("internal_links", 0) < 3:
        tech_score -= 15

    if technical.get("had_redirect"):
        tech_score -= 5

    if not technical.get("lang"):
        tech_score -= 10

    scores["technical"] = max(0, tech_score)

    # --- Schema (15%) ---
    schema_score = 100
    if not schema.get("has_schema"):
        schema_score -= 70
    else:
        # Bonus for rich result eligible types
        rich_types = set(schema.get("types", [])) & {
            "Product", "Article", "FAQPage", "HowTo",
            "BreadcrumbList", "Organization", "WebSite",
        }
        schema_score += min(len(rich_types) * 5, 15)

    scores["schema"] = min(100, max(0, schema_score))

    # --- Weighted Total ---
    weights = {
        "meta": 0.30,
        "headings": 0.15,
        "images": 0.20,
        "technical": 0.20,
        "schema": 0.15,
    }

    total = sum(scores[k] * weights[k] for k in weights)
    scores["total"] = round(total)

    return scores