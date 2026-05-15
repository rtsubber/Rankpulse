"""
BoostRank — Competitor Compare Feature
Compare SEO scores side-by-side with competitors.
"""

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional

from app.database import (
    check_rate_limit, increment_rate_limit, save_audit,
)
from app.auth import get_current_user, get_api_key_user, Security, HTTPAuthorizationCredentials

router = APIRouter(prefix="/api/compare", tags=["compare"])


class CompareRequest(BaseModel):
    url: HttpUrl
    competitors: list[HttpUrl]  # 1-5 competitor URLs


class CompareResult(BaseModel):
    url: str
    seo_score: int
    scores: dict
    issues_count: int
    top_issues: list[dict]


class CompareResponse(BaseModel):
    primary: CompareResult
    competitors: list[CompareResult]
    comparison: dict
    created_at: float


@router.post("", response_model=CompareResponse)
async def compare_sites(
    request: CompareRequest,
    user: dict = Depends(get_current_user),
):
    """Compare SEO scores of your site vs competitors. Pro: 5/week, Agency: unlimited."""
    user_id = user["id"]
    tier = user["tier"]

    if len(request.competitors) < 1 or len(request.competitors) > 5:
        raise HTTPException(status_code=400, detail="Provide 1-5 competitor URLs")

    # Free tier can't use compare
    if tier == "free":
        raise HTTPException(
            status_code=403,
            detail="Competitor comparison requires Pro or Agency plan. Upgrade at https://boostrank.co/pricing",
        )

    # Check rate limit
    allowed, remaining, reset_in = check_rate_limit(user_id, "compare", tier)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Compare limit reached. Resets in {reset_in}s. Upgrade at https://boostrank.co/pricing",
            headers={"Retry-After": str(reset_in)},
        )

    from app.analyzers.fetcher import fetch_page
    from app.analyzers.meta_tags import analyze_meta_tags
    from app.analyzers.headings import analyze_headings
    from app.analyzers.images import analyze_images
    from app.analyzers.technical import analyze_technical
    from app.analyzers.schema_org import analyze_schema
    from app.analyzers.scoring import calculate_seo_score

    async def audit_url(url: str) -> dict:
        """Run a full audit on a URL."""
        html, response_time, final_url = await fetch_page(str(url))

        meta = analyze_meta_tags(html, str(url))
        headings = analyze_headings(html, str(url))
        images = analyze_images(html, str(url))
        technical = analyze_technical(html, str(url), final_url)
        schema = analyze_schema(html, str(url))

        all_issues = (
            meta["issues"] + headings["issues"] +
            images["issues"] + technical["issues"] + schema["issues"]
        )

        scores = calculate_seo_score(meta, headings, images, technical, schema)

        return {
            "url": str(url),
            "seo_score": scores["total"],
            "scores": scores,
            "issues_count": len(all_issues),
            "top_issues": [
                {"severity": i["severity"], "category": i["category"], "message": i["message"]}
                for i in sorted(all_issues, key=lambda x: 0 if x["severity"] == "error" else 1)[:5]
            ],
        }

    # Audit primary URL
    primary_result = await audit_url(request.url)

    # Audit competitors
    competitor_results = []
    for comp_url in request.competitors:
        try:
            comp_result = await audit_url(comp_url)
            competitor_results.append(comp_result)
        except Exception as e:
            competitor_results.append({
                "url": str(comp_url),
                "seo_score": 0,
                "scores": {},
                "issues_count": 0,
                "top_issues": [{"severity": "error", "category": "fetch", "message": str(e)}],
            })

    # Build comparison
    all_scores = [primary_result["seo_score"]] + [c["seo_score"] for c in competitor_results]
    comparison = {
        "rank": sorted(all_scores, reverse=True).index(primary_result["seo_score"]) + 1,
        "score_diff_vs_best": max(all_scores) - primary_result["seo_score"],
        "average_competitor_score": (
            sum(c["seo_score"] for c in competitor_results) / len(competitor_results)
            if competitor_results else 0
        ),
        "categories_behind": _find_weak_categories(primary_result, competitor_results),
        "recommendations": _generate_comparison_recommendations(primary_result, competitor_results),
    }

    # Increment rate limit
    increment_rate_limit(user_id, "compare")

    # Save audit history
    save_audit(
        user_id=user_id, api_key_id=None,
        url=str(request.url), seo_score=primary_result["seo_score"],
        scores=primary_result["scores"], issues=[], page_data={},
        source="compare",
    )

    return CompareResponse(
        primary=primary_result,
        competitors=competitor_results,
        comparison=comparison,
        created_at=time.time(),
    )


def _find_weak_categories(primary: dict, competitors: list[dict]) -> list[str]:
    """Find categories where primary is behind the average competitor."""
    categories = ["meta", "headings", "images", "technical", "schema"]
    weak = []

    for cat in categories:
        primary_score = primary.get("scores", {}).get(cat, 0)
        comp_scores = [
            c.get("scores", {}).get(cat, 0) for c in competitors
            if c.get("seo_score", 0) > 0
        ]
        if comp_scores:
            avg_comp = sum(comp_scores) / len(comp_scores)
            if primary_score < avg_comp - 10:
                weak.append(cat)

    return weak


def _generate_comparison_recommendations(primary: dict, competitors: list[dict]) -> list[str]:
    """Generate actionable recommendations based on comparison."""
    recs = []

    # Score-based
    if primary["seo_score"] < 50:
        recs.append("Your SEO score is below 50 — prioritize fixing errors first")
    elif primary["seo_score"] < 70:
        recs.append("Good foundation — focus on the categories where competitors outscore you")

    # Category-specific
    weak = _find_weak_categories(primary, competitors)
    category_tips = {
        "meta": "Improve meta tags: ensure unique titles (30-60 chars) and descriptions (120-160 chars) on every page",
        "headings": "Fix heading structure: use exactly one H1 per page, with a logical H2-H6 hierarchy",
        "images": "Add alt text to all images — competitors are scoring higher here",
        "technical": "Technical SEO gaps detected: check HTTPS, internal linking, and page speed",
        "schema": "Add structured data (Schema.org) — this enables rich results in search",
    }
    for cat in weak:
        if cat in category_tips:
            recs.append(category_tips[cat])

    # Issue-based
    error_count = primary.get("issues_count", 0)
    if error_count > 10:
        recs.append(f"You have {error_count} issues — start with the {min(error_count, 3)} highest-severity ones")

    return recs[:5]  # Max 5 recommendations