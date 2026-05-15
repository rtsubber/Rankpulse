"""
BoostRank — Authentication Module
Signup, login, JWT tokens, API key auth.
"""

import time
import secrets
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from app.database import (
    get_db, hash_password, verify_password, generate_api_key,
    check_rate_limit, increment_rate_limit, TIER_LIMITS,
)

# --- JWT (lightweight, no external dep) ---

JWT_SECRET = secrets.token_hex(32)  # Rotate on restart; fine for single-instance
JWT_ALGO = "HS256"
JWT_EXPIRY = 86400 * 7  # 7 days


def _b64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_jwt(payload: dict) -> str:
    """Create a simple JWT token."""
    import hashlib, hmac
    import json as _json

    header = {"alg": JWT_ALGO, "typ": "JWT"}
    segments = [
        _b64url_encode(_json.dumps(header, separators=(',', ':')).encode()),
        _b64url_encode(_json.dumps(payload, separators=(',', ':')).encode()),
    ]
    signing_input = f"{segments[0]}.{segments[1]}".encode()
    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def verify_jwt(token: str) -> dict | None:
    """Verify and decode a JWT token. Returns payload or None."""
    import hashlib, hmac

    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        # Verify signature
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        signature = _b64url_decode(parts[2])
        expected = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None

        # Safe JSON decode instead of eval
        import json
        payload = json.loads(_b64url_decode(parts[1]).decode())

        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# --- Models ---

class SignupRequest(BaseModel):
    email: EmailStr
    password: str  # min 8 chars enforced in route
    name: str = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    tier: str
    created_at: float

class APIKeyResponse(BaseModel):
    id: int
    key: str  # Only shown on creation
    prefix: str
    name: str
    tier: str
    monthly_limit: int | None
    created_at: float

class TierInfoResponse(BaseModel):
    tier: str
    limits: dict


# --- Route handlers ---

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict:
    """Dependency: extract user from JWT bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_jwt(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (payload["sub"],)).fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return dict(user)


async def get_api_key_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict | None:
    """Dependency: extract user from API key (Bearer token). Returns None if no key."""
    if not credentials:
        return None

    # Try JWT first
    payload = verify_jwt(credentials.credentials)
    if payload:
        conn = get_db()
        try:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (payload["sub"],)).fetchone()
        finally:
            conn.close()
        if user:
            return dict(user)

    # Try API key
    key_hash = __import__("hashlib").sha256(credentials.credentials.encode()).hexdigest()
    conn = get_db()
    try:
        key_row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (key_hash,),
        ).fetchone()
    finally:
        conn.close()

    if not key_row:
        return None

    # Check monthly limit
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (key_row["user_id"],)).fetchone()
    finally:
        conn.close()

    if not user:
        return None

    return {**dict(user), "api_key_id": key_row["id"], "api_key_tier": key_row["tier"]}


def signup(request: SignupRequest) -> dict:
    """Register a new user."""
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    conn = get_db()
    try:
        # Check if email exists
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (request.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        pw_hash = hash_password(request.password)
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (request.email, pw_hash, request.name),
        )
        conn.commit()
        user_id = cursor.lastrowid

        token = create_jwt({"sub": user_id, "email": request.email, "exp": time.time() + JWT_EXPIRY})

        return {
            "user": {"id": user_id, "email": request.email, "name": request.name, "tier": "free"},
            "token": token,
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


def login(request: LoginRequest) -> dict:
    """Authenticate a user."""
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (request.email,)).fetchone()
    finally:
        conn.close()

    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_jwt({"sub": user["id"], "email": user["email"], "exp": time.time() + JWT_EXPIRY})

    # Update last login
    conn = get_db()
    try:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (time.time(), user["id"]))
        conn.commit()
    finally:
        conn.close()

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "tier": user["tier"],
        },
        "token": token,
    }


def create_api_key(user_id: int, name: str = "Default", tier: str | None = None) -> dict:
    """Generate a new API key for a user."""
    conn = get_db()
    try:
        user = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        effective_tier = tier or user["tier"]
        raw_key, key_hash, key_prefix = generate_api_key()
        monthly_limit = TIER_LIMITS.get(effective_tier, TIER_LIMITS["free"])["api_per_month"]

        cursor = conn.execute(
            """INSERT INTO api_keys (user_id, key_hash, key_prefix, name, tier, monthly_limit, last_reset)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, key_hash, key_prefix, name, effective_tier, monthly_limit if monthly_limit > 0 else None, time.time()),
        )
        conn.commit()

        return {
            "id": cursor.lastrowid,
            "key": raw_key,
            "prefix": key_prefix,
            "name": name,
            "tier": effective_tier,
            "monthly_limit": monthly_limit if monthly_limit > 0 else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


def list_api_keys(user_id: int) -> list[dict]:
    """List API keys for a user (without revealing the full key)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, key_prefix, name, tier, monthly_limit, created_at FROM api_keys WHERE user_id = ? AND revoked_at IS NULL",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def revoke_api_key(user_id: int, key_id: int):
    """Revoke an API key."""
    conn = get_db()
    try:
        result = conn.execute(
            "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND user_id = ?",
            (time.time(), key_id, user_id),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="API key not found")
    finally:
        conn.close()


def get_tier_info(user_id: int) -> dict:
    """Get user's tier and limits."""
    conn = get_db()
    try:
        user = conn.execute("SELECT tier FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tier = user["tier"]
    limits = TIER_LIMITS[tier]

    # Format limits for display (-1 = "unlimited")
    display = {}
    for k, v in limits.items():
        display[k] = "unlimited" if v == -1 else v

    return {"tier": tier, "limits": display}