"""
RankPulse — SEO Analysis API
FastAPI backend for e-commerce SEO auditing.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import time

from app.analyzers.meta_tags import analyze_meta_tags
from app.analyzers.headings import analyze_headings
from app.analyzers.images import analyze_images
from app.analyzers.technical import analyze_technical
from app.analyzers.schema_org import analyze_schema
from app.analyzers.scoring import calculate_seo_score

app = FastAPI(
    title="RankPulse API",
    description="Instant SEO audits for e-commerce stores",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class AuditRequest(BaseModel):
    url: HttpUrl
    include_lighthouse: bool = False  # Optional slow Lighthouse run

class AuditIssue(BaseModel):
    severity: str  # "critical", "warning", "info"
    category: str  # "meta", "headings", "images", "technical", "schema"
    message: str
    detail: Optional[str] = None
    fix: Optional[str] = None  # How to fix it

class AuditResponse(BaseModel):
    url: str
    timestamp: float
    seo_score: int  # 0-100
    scores: dict  # Breakdown by category
    issues: list[AuditIssue]
    page_data: dict  # Extracted metadata


# --- Endpoints ---

@app.get("/")
async def root():
    return {"name": "RankPulse", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/api/audit", response_model=AuditResponse)
async def audit_page(request: AuditRequest):
    """Full SEO audit of a single page."""
    url = str(request.url)

    try:
        # Fetch page content
        from app.analyzers.fetcher import fetch_page
        html, response_time, final_url = await fetch_page(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch page: {str(e)}")

    # Run all analyzers
    meta_results = analyze_meta_tags(html, url)
    heading_results = analyze_headings(html, url)
    image_results = analyze_images(html, url)
    technical_results = analyze_technical(html, url, final_url)
    schema_results = analyze_schema(html, url)

    # Combine issues
    all_issues = (
        meta_results["issues"] +
        heading_results["issues"] +
        image_results["issues"] +
        technical_results["issues"] +
        schema_results["issues"]
    )

    # Calculate scores
    scores = calculate_seo_score(
        meta_results, heading_results, image_results,
        technical_results, schema_results
    )

    # Page data summary
    page_data = {
        "title": meta_results.get("title", ""),
        "description": meta_results.get("description", ""),
        "canonical": meta_results.get("canonical", ""),
        "og_title": meta_results.get("og_title", ""),
        "og_image": meta_results.get("og_image", ""),
        "h1_count": heading_results.get("h1_count", 0),
        "total_headings": heading_results.get("total_count", 0),
        "image_count": image_results.get("total", 0),
        "images_missing_alt": image_results.get("missing_alt", 0),
        "has_schema": schema_results.get("has_schema", False),
        "schema_types": schema_results.get("types", []),
        "response_time_ms": response_time,
        "final_url": final_url,
    }

    return AuditResponse(
        url=url,
        timestamp=time.time(),
        seo_score=scores["total"],
        scores=scores,
        issues=all_issues,
        page_data=page_data,
    )


@app.post("/api/quick-check")
async def quick_check(url: HttpUrl = Query(..., description="URL to check")):
    """Fast meta + heading check (no images, no schema)."""
    url_str = str(url)

    try:
        from app.analyzers.fetcher import fetch_page
        html, response_time, final_url = await fetch_page(url_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch: {str(e)}")

    meta = analyze_meta_tags(html, url_str)
    headings = analyze_headings(html, url_str)

    return {
        "url": url_str,
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "title_length": meta.get("title_length", 0),
        "description_length": meta.get("description_length", 0),
        "h1_count": headings.get("h1_count", 0),
        "heading_structure": headings.get("structure", []),
        "issues": meta["issues"] + headings["issues"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)