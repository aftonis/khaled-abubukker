"""
Identity-Aware Agent Authentication
====================================
Implements the "Identity Aware Agent Development Requirement" from the spec.

Each agent gets:
  - A signed JWT with role + permissions claims
  - A scoped permission set (read-only, write, admin)
  - An audit trail entry for every decision
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import jwt
import bcrypt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

AGENT_SIGNING_KEY = os.getenv("AGENT_SIGNING_KEY") or secrets.token_urlsafe(32)


# --- Agent identity registry ---

AGENT_PERMISSIONS = {
    "telemetry_ingestion": {
        "role": "Telemetry Ingestion Specialist",
        "permissions": ["read:devices", "read:sensor_readings", "write:sensor_readings"],
    },
    "device_health": {
        "role": "Device Health Monitor",
        "permissions": ["read:devices", "read:sensor_readings", "write:alerts"],
    },
    "anomaly_detector": {
        "role": "Anomaly Detection Specialist",
        "permissions": ["read:sensor_readings", "write:alerts"],
    },
    "security": {
        "role": "Security Operations Agent",
        "permissions": ["read:devices", "read:sensor_readings", "write:incidents", "write:alerts"],
    },
    "incident_classifier": {
        "role": "Incident Classification Specialist",
        "permissions": ["read:alerts", "write:incidents"],
    },
    "response_recommender": {
        "role": "Response Recommendation Engine",
        "permissions": ["read:incidents", "read:alerts", "write:incidents"],
    },
    "validator": {
        "role": "Decision Validator / Reviewer",
        "permissions": ["read:agent_task_logs", "write:agent_task_logs"],
    },
}


def issue_agent_token(agent_name: str) -> str:
    """Issue a signed JWT identity token for an agent."""
    if agent_name not in AGENT_PERMISSIONS:
        raise ValueError(f"Unknown agent: {agent_name}. Known: {list(AGENT_PERMISSIONS)}")

    profile = AGENT_PERMISSIONS[agent_name]
    payload = {
        "sub": agent_name,
        "role": profile["role"],
        "permissions": profile["permissions"],
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES),
        "type": "agent_identity",
    }
    return jwt.encode(payload, AGENT_SIGNING_KEY, algorithm=JWT_ALGORITHM)


def verify_agent_token(token: str) -> Optional[Dict]:
    """Verify an agent token and return its claims, or None if invalid."""
    try:
        return jwt.decode(token, AGENT_SIGNING_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    """SHA-256 hash of token for audit logging (never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()


def has_permission(token: str, required_permission: str) -> bool:
    """Check if an agent token grants a specific permission."""
    claims = verify_agent_token(token)
    if not claims:
        return False
    return required_permission in claims.get("permissions", [])


# --- User auth (for dashboard admin page) ---

def hash_password(password: str) -> str:
    # Truncate to bcrypt's 72-byte max defensively
    pw_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


def issue_user_token(username: str, role: str = "operator") -> str:
    """Issue a JWT for a human user (dashboard auth)."""
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES),
        "type": "user",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_user_token(token: str) -> Optional[Dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# --- Default admin (for demo) ---
DEFAULT_USERS = {
    os.getenv("ADMIN_USERNAME", "admin"): {
        "password_hash": hash_password(os.getenv("ADMIN_PASSWORD", "admin123")),
        "role": "admin",
    },
    "operator": {
        "password_hash": hash_password("operator123"),
        "role": "operator",
    },
}


def authenticate_user(username: str, password: str) -> Optional[str]:
    """Returns JWT token if credentials valid, else None."""
    user = DEFAULT_USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return issue_user_token(username, user["role"])


if __name__ == "__main__":
    # Smoke test
    print("=== Agent Identity Test ===")
    for agent in AGENT_PERMISSIONS:
        token = issue_agent_token(agent)
        claims = verify_agent_token(token)
        print(f"  {agent}: role={claims['role']}, perms={len(claims['permissions'])}")

    print("\n=== Permission Check ===")
    sec_token = issue_agent_token("security")
    print(f"  security can write:incidents → {has_permission(sec_token, 'write:incidents')}")
    print(f"  security can write:devices → {has_permission(sec_token, 'write:devices')}")

    print("\n=== User Auth Test ===")
    tok = authenticate_user("admin", "admin123")
    print(f"  admin login → {tok[:40]}...")
    tok = authenticate_user("admin", "wrong")
    print(f"  bad login → {tok}")
