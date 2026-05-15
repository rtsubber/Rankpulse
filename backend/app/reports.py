"""
BoostRank — Weekly PDF Report Generator
Generates branded SEO audit reports for Pro and Agency users.
Agency users can white-label reports.
"""

import time
import json
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import (
    get_db, get_audit_by_id, get_user_audits,
    check_rate_limit, increment_rate_limit, save_audit,
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportRequest(BaseModel):
    audit_id: int | None = None  # Specific audit, or latest if None
    url: str | None = None  # URL to audit if no audit_id
    branding: dict | None = None  # White-label: {"company": "...", "logo_url": "...", "color": "..."}


@router.get("/history")
async def get_report_history(
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """Get audit history for the current user."""
    audits = get_user_audits(user["id"], limit=limit, offset=offset)
    return {"audits": audits, "total": len(audits)}


@router.post("/pdf")
async def generate_pdf_report(
    request: ReportRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a PDF report. Pro: 1/week, Agency: unlimited."""
    tier = user["tier"]

    if tier == "free":
        raise HTTPException(
            status_code=403,
            detail="PDF reports require Pro or Agency plan. Upgrade at https://boostrank.co/pricing",
        )

    # Check rate limit
    allowed, remaining, reset_in = check_rate_limit(user["id"], "report", tier)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Report limit reached. Resets in {reset_in}s.",
            headers={"Retry-After": str(reset_in)},
        )

    # Get audit data
    audit = None
    if request.audit_id:
        audit = get_audit_by_id(request.audit_id)
        if not audit or (audit.get("user_id") and audit["user_id"] != user["id"]):
            raise HTTPException(status_code=404, detail="Audit not found")
    elif request.url:
        # Run a new audit
        audit = await _run_audit(str(request.url), user["id"])
    else:
        # Get the latest audit
        audits = get_user_audits(user["id"], limit=1)
        if audits:
            audit = get_audit_by_id(audits[0]["id"])
        if not audit:
            raise HTTPException(status_code=404, detail="No audits found. Run an audit first.")

    # Generate PDF
    branding = request.branding if tier == "agency" else None
    pdf_bytes = _build_pdf(audit, user, branding)

    # Increment rate limit
    increment_rate_limit(user["id"], "report")

    # Save audit if it was a new one
    if not request.audit_id:
        save_audit(
            user_id=user["id"], api_key_id=None,
            url=audit["url"], seo_score=audit["seo_score"],
            scores=audit["scores"], issues=audit["issues"],
            page_data=audit["page_data"], source="report",
        )

    filename = f"boostrank-report-{audit['url'].replace('://', '-').replace('/', '_')[:50]}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _run_audit(url: str, user_id: int) -> dict:
    """Run a full audit and return the result."""
    from app.analyzers.fetcher import fetch_page
    from app.analyzers.meta_tags import analyze_meta_tags
    from app.analyzers.headings import analyze_headings
    from app.analyzers.images import analyze_images
    from app.analyzers.technical import analyze_technical
    from app.analyzers.schema_org import analyze_schema
    from app.analyzers.scoring import calculate_seo_score

    html, response_time, final_url = await fetch_page(url)

    meta = analyze_meta_tags(html, url)
    headings = analyze_headings(html, url)
    images = analyze_images(html, url)
    technical = analyze_technical(html, url, final_url)
    schema = analyze_schema(html, url)

    all_issues = (
        meta["issues"] + headings["issues"] +
        images["issues"] + technical["issues"] + schema["issues"]
    )

    scores = calculate_seo_score(meta, headings, images, technical, schema)

    page_data = {
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "h1_count": headings.get("h1_count", 0),
        "image_count": images.get("total", 0),
        "images_missing_alt": images.get("missing_alt", 0),
        "has_schema": schema.get("has_schema", False),
        "response_time_ms": response_time,
    }

    return {
        "url": url,
        "seo_score": scores["total"],
        "scores": scores,
        "issues": all_issues,
        "page_data": page_data,
        "created_at": time.time(),
    }


def _build_pdf(audit: dict, user: dict, branding: dict | None = None) -> bytes:
    """Build a PDF report using reportlab (or fallback to HTML-to-PDF)."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
    except ImportError:
        # Fallback: return a minimal PDF using raw PDF generation
        return _build_pdf_minimal(audit, user, branding)

    buffer = io.BytesIO()

    # Branding
    brand_name = "BoostRank" if not branding else branding.get("company", "BoostRank")
    brand_color = HexColor("#4F46E5") if not branding else HexColor(branding.get("color", "#4F46E5"))
    brand_logo = branding.get("logo_url") if branding else None

    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "BrandTitle", parent=styles["Title"],
        fontSize=24, textColor=brand_color, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "BrandSub", parent=styles["Normal"],
        fontSize=11, textColor=colors.grey, spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        "ScoreBig", parent=styles["Title"],
        fontSize=48, textColor=brand_color, alignment=1, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Heading2"],
        fontSize=14, textColor=brand_color, spaceBefore=14, spaceAfter=6,
    ))

    story = []

    # Header
    story.append(Paragraph(f"{brand_name} SEO Audit Report", styles["BrandTitle"]))
    report_date = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(
        f"URL: {audit['url']} | Date: {report_date} | Prepared for: {user.get('name', user['email'])}",
        styles["BrandSub"],
    ))
    story.append(Spacer(1, 20))

    # Big Score
    score = audit["seo_score"]
    score_color = HexColor("#10B981") if score >= 70 else HexColor("#F59E0B") if score >= 50 else HexColor("#EF4444")
    styles.add(ParagraphStyle("ScoreValue", parent=styles["Title"], fontSize=72, textColor=score_color, alignment=1))
    story.append(Paragraph(f"{score}", styles["ScoreValue"]))
    story.append(Paragraph("SEO Score", styles["BrandSub"]))
    story.append(Spacer(1, 20))

    # Category Scores Table
    scores = audit.get("scores", {})
    story.append(Paragraph("Category Breakdown", styles["SectionHead"]))

    cat_data = [["Category", "Score", "Weight", "Weighted"]]
    weights = {"meta": "30%", "headings": "15%", "images": "20%", "technical": "20%", "schema": "15%"}
    for cat, weight_label in weights.items():
        s = scores.get(cat, 0)
        cat_data.append([
            cat.title(),
            f"{s}/100",
            weight_label,
            f"{s * float(weight_label.strip('%')) / 100:.0f}",
        ])
    cat_data.append(["Total", f"{score}/100", "100%", f"{score}"])

    cat_table = Table(cat_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    cat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F9FAFB")]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 20))

    # Issues
    issues = audit.get("issues", [])
    if issues:
        story.append(Paragraph(f"Issues Found ({len(issues)})", styles["SectionHead"]))

        # Group by severity
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        infos = [i for i in issues if i.get("severity") not in ("error", "warning")]

        for label, group in [("🔴 Errors", errors), ("🟡 Warnings", warnings), ("ℹ️ Info", infos)]:
            if not group:
                continue
            story.append(Paragraph(label, styles["Heading3"]))
            for issue in group[:10]:  # Max 10 per group
                msg = issue.get("message", "Unknown issue")
                fix = issue.get("fix", "")
                line = f"• {msg}"
                if fix:
                    line += f" → <b>Fix:</b> {fix}"
                story.append(Paragraph(line, styles["Normal"]))
            if len(group) > 10:
                story.append(Paragraph(f"  ...and {len(group) - 10} more", styles["Normal"]))

    # Footer
    story.append(Spacer(1, 30))
    footer_text = f"Generated by {brand_name} — https://boostrank.co"
    if branding:
        footer_text += f" | White-label report for {branding.get('company', '')}"
    story.append(Paragraph(footer_text, styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()


def _build_pdf_minimal(audit: dict, user: dict, branding: dict | None = None) -> bytes:
    """Minimal PDF generation without reportlab dependency."""
    # Generate a simple PDF manually (basic PDF 1.4 format)
    brand_name = "BoostRank" if not branding else branding.get("company", "BoostRank")
    score = audit["seo_score"]
    url = audit["url"]
    date = datetime.now().strftime("%B %d, %Y")
    scores = audit.get("scores", {})

    lines = [
        f"{brand_name} SEO Audit Report",
        f"",
        f"URL: {url}",
        f"Date: {date}",
        f"SEO Score: {score}/100",
        f"",
        "Category Scores:",
    ]
    for cat, val in scores.items():
        if cat != "total":
            lines.append(f"  {cat.title()}: {val}/100")

    lines.append("")
    issues = audit.get("issues", [])
    lines.append(f"Issues Found: {len(issues)}")
    for issue in issues[:15]:
        lines.append(f"  [{issue.get('severity', '?').upper()}] {issue.get('message', '')}")

    lines.append(f"\nGenerated by {brand_name} - https://boostrank.co")

    content = "\n".join(lines)

    # Minimal PDF
    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n")
    pdf.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    pdf.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    pdf.write(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n")

    # Content stream
    stream_lines = ["BT", "/F1 12 Tf"]
    y = 750
    for line in content.split("\n"):
        if y < 50:
            break
        escaped = line.replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"1 0 0 1 50 {y} Tm")
        stream_lines.append(f"({escaped}) Tj")
        y -= 16

    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode()

    pdf.write(f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode())
    pdf.write(stream)
    pdf.write(b"\nendstream\nendobj\n")
    pdf.write(b"xref\n0 5\n0000000000 65535 f \n")
    pdf.write(b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n")

    return pdf.getvalue()