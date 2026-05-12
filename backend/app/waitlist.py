"""BoostRank Waitlist — stores emails in Google Sheets."""
import os
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter()

# Google Sheets config
SPREADSHEET_ID = os.environ.get("BOOSTRANK_SHEET_ID", "")
SHEET_NAME = os.environ.get("BOOSTRANK_SHEET_NAME", "Waitlist")
SA_CREDENTIALS = os.environ.get("GOOGLE_SA_CREDENTIALS", "")

# Fallback: local file for dev/testing
WAITLIST_FILE = Path("/tmp/boostrank_waitlist.json")


class WaitlistEntry(BaseModel):
    email: EmailStr


def get_sheets_service():
    """Create Google Sheets service from env var credentials."""
    if not SA_CREDENTIALS:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        creds_info = json.loads(SA_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return build("sheets", "v4", credentials=creds)
    except Exception:
        return None


def append_to_sheet(email: str, source: str = "landing_page"):
    """Append a row to the Google Sheet."""
    service = get_sheets_service()
    if not service or not SPREADSHEET_ID:
        return False
    
    timestamp = datetime.utcnow().isoformat()
    values = [[email, timestamp, source]]
    
    try:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:C",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        return True
    except Exception:
        return False


def get_sheet_entries():
    """Get all entries from the Google Sheet."""
    service = get_sheets_service()
    if not service or not SPREADSHEET_ID:
        return []
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:C",
        ).execute()
        rows = result.get("values", [])
        # Skip header row if present
        entries = []
        for row in rows:
            if len(row) >= 2 and "@" in row[0]:
                entries.append({
                    "email": row[0],
                    "joined_at": row[1] if len(row) > 1 else "",
                    "source": row[2] if len(row) > 2 else "",
                })
        return entries
    except Exception:
        return []


def append_to_local(email: str, source: str = "landing_page"):
    """Fallback: save to local JSON file."""
    entries = []
    if WAITLIST_FILE.exists():
        try:
            entries = json.loads(WAITLIST_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            entries = []

    if any(e.get("email") == email for e in entries):
        return False

    entries.append({
        "email": email,
        "joined_at": datetime.utcnow().isoformat(),
        "source": source,
    })
    WAITLIST_FILE.write_text(json.dumps(entries, indent=2))
    return True


@router.post("/api/waitlist")
async def join_waitlist(entry: WaitlistEntry):
    email = entry.email.lower()

    # Try Google Sheets first, fall back to local
    sheet_ok = append_to_sheet(email)
    local_ok = append_to_local(email)

    if not sheet_ok and not local_ok:
        return {"message": "Already on waitlist!", "email": email}

    return {"message": "Welcome aboard! You're on the waitlist.", "email": email}


@router.get("/api/waitlist")
async def get_waitlist():
    """Get all waitlist entries (admin)."""
    # Try Google Sheets first
    sheet_entries = get_sheet_entries()
    if sheet_entries:
        return {"count": len(sheet_entries), "entries": sheet_entries, "source": "google_sheets"}
    
    # Fallback to local
    entries = []
    if WAITLIST_FILE.exists():
        try:
            entries = json.loads(WAITLIST_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            entries = []
    return {"count": len(entries), "entries": entries, "source": "local_file"}
