"""Schema.org / JSON-LD analyzer — detect and validate structured data."""

import json
from bs4 import BeautifulSoup

# Schema types that qualify for rich results
RICH_RESULT_TYPES = {
    "Product", "Article", "BreadcrumbList", "FAQPage",
    "HowTo", "VideoObject", "ImageObject", "Organization",
    "WebSite", "LocalBusiness", "Review", "Recipe",
    "Event", "Course", "JobPosting", "FAQPage",
}

# Required properties by schema type
REQUIRED_PROPS = {
    "Product": ["name", "image", "description", "offers"],
    "Article": ["headline", "image", "datePublished", "author"],
    "Organization": ["name", "url"],
    "WebSite": ["name", "url"],
    "BreadcrumbList": ["itemListElement"],
    "FAQPage": ["mainEntity"],
    "HowTo": ["name", "step"],
}

def analyze_schema(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    issues = []

    # Find all JSON-LD blocks
    scripts = soup.find_all("script", type="application/ld+json")
    has_schema = len(scripts) > 0
    types = []
    all_schemas = []
    errors = []

    for script in scripts:
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            errors.append("Invalid JSON-LD block found (parse error)")
            continue

        # Handle @graph arrays
        if isinstance(data, dict) and "@graph" in data:
            items = data["@graph"]
        elif isinstance(data, list):
            items = data
        else:
            items = [data]

        for item in items:
            schema_type = item.get("@type", "")
            if isinstance(schema_type, list):
                schema_type = schema_type[0]

            types.append(schema_type)
            all_schemas.append(item)

            # Check required properties
            if schema_type in REQUIRED_PROPS:
                missing = []
                for prop in REQUIRED_PROPS[schema_type]:
                    if prop not in item:
                        missing.append(prop)
                if missing:
                    issues.append({
                        "severity": "warning",
                        "category": "schema",
                        "message": f"{schema_type} schema missing required properties: {', '.join(missing)}",
                        "detail": f"Required: {', '.join(REQUIRED_PROPS[schema_type])}",
                        "fix": f"Add the missing properties to your {schema_type} schema: {', '.join(missing)}",
                    })

            # Check for rich result eligibility
            if schema_type in RICH_RESULT_TYPES:
                issues.append({
                    "severity": "info",
                    "category": "schema",
                    "message": f"✅ {schema_type} schema detected — eligible for rich results",
                    "detail": f"Google may show enhanced search results for this {schema_type} schema.",
                    "fix": None,
                })

    if not has_schema:
        issues.append({
            "severity": "critical",
            "category": "schema",
            "message": "No structured data (JSON-LD) found",
            "detail": "Schema.org markup helps Google understand your content and enables rich results.",
            "fix": "Add JSON-LD schema for your content type (Product, Article, etc.).",
        })

    if errors:
        for error in errors:
            issues.append({
                "severity": "critical",
                "category": "schema",
                "message": error,
                "detail": "Google may ignore malformed structured data.",
                "fix": "Validate your JSON-LD at schema.org or Google's Rich Results Test.",
            })

    # E-commerce specific: check for Product schema
    is_ecommerce = "Product" not in types
    if has_schema and is_ecommerce and "product" in url.lower():
        issues.append({
            "severity": "warning",
            "category": "schema",
            "message": "Product page without Product schema",
            "detail": "URL contains 'product' but no Product schema was found.",
            "fix": "Add Product schema with name, image, description, price, and availability.",
        })

    return {
        "has_schema": has_schema,
        "types": types,
        "schema_count": len(all_schemas),
        "issues": issues,
    }