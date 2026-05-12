"""BoostRank Waitlist — stores emails in Google Sheets via OAuth."""
import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter()

SPREADSHEET_ID = "10Kk1wUY9k78NKi9fcRAjDGF082qhkIOeJohhCzXL78I"
SHEET_NAME = "Sheet1"

# OAuth token file (shared with main system)
OAUTH_TOKEN_FILE = os.environ.get("BOOSTRANK_OAUTH_FILE", "/tmp/boostrank_oauth.json")
# Fallback local file
WAITLIST_FILE = Path("/tmp/boostrank_waitlist.json")


class WaitlistEntry(BaseModel):
    email: EmailStr


def get_access_token():
    """Get a fresh access token from the OAuth refresh token."""
    token_path = Path.home() / ".openclaw" / "workspace" / ".gmail_oauth_ets.json"
    try:
        with open(token_path) as f:
            d = json.load(f)
        
        # Check if token is still valid
        if d.get('expires_at', 0) > time.time() + 60:
            return d.get('access_token')
        
        # Refresh the token
        with open(Path.home() / ".openclaw" / "workspace" / ".google_client_secret.json") as f:
            client = json.load(f)
        inst = client.get('installed', client)
        
        resp = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': inst['client_id'],
            'client_secret': inst['client_secret'],
            'refresh_token': d['refresh_token'],
            'grant_type': 'refresh_token',
        }, timeout=15)
        
        if resp.status_code == 200:
            tokens = resp.json()
            d['access_token'] = tokens['access_token']
            d['expires_at'] = time.time() + tokens.get('expires_in', 3600)
            with open(token_path, 'w') as f:
                json.dump(d, f, indent=2)
            return tokens['access_token']
    except Exception:
        pass
    return None


def append_to_sheet(email: str, source: str = "landing_page"):
    """Append a row to the Google Sheet."""
    access_token = get_access_token()
    if not access_token:
        return False
    
    timestamp = datetime.utcnow().isoformat()
    values = [[email, timestamp, source]]
    
    try:
        resp = requests.post(
            f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!A:C:append',
            params={'valueInputOption': 'USER_ENTERED', 'insertDataOption': 'INSERT_ROWS'},
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json={'values': values},
            timeout=15
        )
        return resp.status_code == 200
    except Exception:
        return False


def get_sheet_entries():
    """Get all entries from the Google Sheet."""
    access_token = get_access_token()
    if not access_token:
        return []
    
    try:
        resp = requests.get(
            f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!A2:C',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15
        )
        if resp.status_code == 200:
            rows = resp.json().get('values', [])
            entries = []
            for row in rows:
                if len(row) >= 1 and row[0]:
                    entries.append({
                        "email": row[0],
                        "joined_at": row[1] if len(row) > 1 else "",
                        "source": row[2] if len(row) > 2 else "",
                    })
            return entries
    except Exception:
        pass
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
    sheet_ok = append_to_sheet(email)
    local_ok = append_to_local(email)

    if not sheet_ok and not local_ok:
        return {"message": "Already on waitlist!", "email": email}

    return {"message": "Welcome aboard! You're on the waitlist.", "email": email}


@router.get("/api/waitlist")
async def get_waitlist():
    """Get all waitlist entries (admin)."""
    sheet_entries = get_sheet_entries()
    if sheet_entries:
        return {"count": len(sheet_entries), "entries": sheet_entries, "source": "google_sheets"}
    
    entries = []
    if WAITLIST_FILE.exists():
        try:
            entries = json.loads(WAITLIST_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            entries = []
    return {"count": len(entries), "entries": entries, "source": "local_file"}
