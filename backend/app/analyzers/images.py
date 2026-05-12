"""Image analyzer — alt text, file names, lazy loading."""

from bs4 import BeautifulSoup

def analyze_images(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    issues = []

    images = soup.find_all("img")
    total = len(images)
    missing_alt = 0
    empty_alt = 0
    bad_filenames = 0
    no_lazy = 0
    no_dimensions = 0

    for img in images:
        src = img.get("src", "")
        alt = img.get("alt")

        # Missing alt
        if alt is None:
            missing_alt += 1
        elif alt.strip() == "":
            empty_alt += 1

        # Bad filenames (numbers, hashes, no extension)
        if src and not src.startswith("data:"):
            filename = src.split("/")[-1].split("?")[0]
            if len(filename) > 40 or any(c in filename for c in ["%", "(", ")"]):
                bad_filenames += 1

        # Lazy loading
        loading = img.get("loading", "")
        if loading != "lazy" and total > 5:
            no_lazy += 1

        # Width/height attributes
        if not img.get("width") or not img.get("height"):
            no_dimensions += 1

    # Generate issues
    if total == 0:
        issues.append({
            "severity": "info",
            "category": "images",
            "message": "No images found on this page",
            "detail": "Pages with relevant images tend to rank better.",
            "fix": "Add product images, diagrams, or infographics to improve engagement.",
        })
    else:
        if missing_alt > 0:
            issues.append({
                "severity": "critical",
                "category": "images",
                "message": f"{missing_alt} image(s) missing alt text",
                "detail": f"{missing_alt} of {total} images have no alt attribute.",
                "fix": "Add descriptive alt text to all images. Include relevant keywords naturally.",
            })

        if empty_alt > 0:
            issues.append({
                "severity": "info",
                "category": "images",
                "message": f"{empty_alt} image(s) have empty alt text",
                "detail": "Empty alt='' is valid for decorative images but should be intentional.",
                "fix": "Use empty alt only for decorative images. Add descriptive alt for content images.",
            })

        if bad_filenames > 0:
            issues.append({
                "severity": "warning",
                "category": "images",
                "message": f"{bad_filenames} image(s) have unoptimized filenames",
                "detail": "Filenames like 'IMG_1234.jpg' or long hash strings don't help SEO.",
                "fix": "Rename images with descriptive keywords: 'red-running-shoes.jpg' instead of 'IMG_1234.jpg'.",
            })

        if no_lazy > 3 and total > 5:
            issues.append({
                "severity": "info",
                "category": "images",
                "message": f"{no_lazy} image(s) not using lazy loading",
                "detail": f"Only {total - no_lazy} of {total} images use loading='lazy'.",
                "fix": "Add loading='lazy' to images below the fold to improve page speed.",
            })

        if no_dimensions > 0:
            issues.append({
                "severity": "info",
                "category": "images",
                "message": f"{no_dimensions} image(s) missing width/height attributes",
                "detail": "Without dimensions, the browser can't reserve space, causing layout shifts (CLS).",
                "fix": "Add width and height attributes to all <img> tags.",
            })

    return {
        "total": total,
        "missing_alt": missing_alt,
        "empty_alt": empty_alt,
        "bad_filenames": bad_filenames,
        "no_lazy": no_lazy,
        "no_dimensions": no_dimensions,
        "issues": issues,
    }