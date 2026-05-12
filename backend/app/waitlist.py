"""BoostRank Waitlist — stores emails in a JSON file."""
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from pathlib import Path
import json
from datetime import datetime

router = APIRouter()
WAITLIST_FILE = Path("/tmp/boostrank_waitlist.json")


class WaitlistEntry(BaseModel):
    email: EmailStr


@router.post("/api/waitlist")
async def join_waitlist(entry: WaitlistEntry):
    email = entry.email.lower()

    # Load existing
    entries = []
    if WAITLIST_FILE.exists():
        try:
            entries = json.loads(WAITLIST_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            entries = []

    # Check duplicate
    if any(e.get("email") == email for e in entries):
        return {"message": "Already on waitlist!", "email": email}

    # Add
    entries.append({
        "email": email,
        "joined_at": datetime.utcnow().isoformat(),
        "source": "landing_page",
    })
    WAITLIST_FILE.write_text(json.dumps(entries, indent=2))

    return {"message": "Welcome aboard! You're on the waitlist.", "email": email}


@router.get("/api/waitlist")
async def get_waitlist():
    """Get all waitlist entries (admin)."""
    entries = []
    if WAITLIST_FILE.exists():
        try:
            entries = json.loads(WAITLIST_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            entries = []
    return {"count": len(entries), "entries": entries}