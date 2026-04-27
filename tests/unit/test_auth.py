"""Unit tests for the identity-aware agent auth layer."""
import pytest
from backend.auth.identity import (
    issue_agent_token, verify_agent_token, has_permission,
    issue_user_token, verify_user_token, hash_token,
    authenticate_user, hash_password, verify_password,
    AGENT_PERMISSIONS,
)


def test_all_known_agents_have_permissions():
    expected_agents = {
        "telemetry_ingestion", "device_health", "anomaly_detector",
        "security", "incident_classifier", "response_recommender", "validator"
    }
    assert set(AGENT_PERMISSIONS.keys()) == expected_agents


def test_issue_and_verify_agent_token():
    token = issue_agent_token("security")
    claims = verify_agent_token(token)
    assert claims["sub"] == "security"
    assert claims["type"] == "agent_identity"
    assert "write:incidents" in claims["permissions"]


def test_unknown_agent_rejected():
    with pytest.raises(ValueError):
        issue_agent_token("evil_agent")


def test_invalid_token_returns_none():
    assert verify_agent_token("not.a.real.token") is None
    assert verify_agent_token("") is None


def test_permission_check():
    sec = issue_agent_token("security")
    assert has_permission(sec, "write:incidents") is True
    assert has_permission(sec, "write:devices") is False
    # Anomaly detector should NOT have write:incidents
    anom = issue_agent_token("anomaly_detector")
    assert has_permission(anom, "write:incidents") is False
    assert has_permission(anom, "write:alerts") is True


def test_hash_token_deterministic():
    t = issue_agent_token("validator")
    h1 = hash_token(t)
    h2 = hash_token(t)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_password_hash_and_verify():
    h = hash_password("test123")
    assert verify_password("test123", h) is True
    assert verify_password("wrong", h) is False


def test_user_authentication():
    tok = authenticate_user("admin", "admin123")
    assert tok is not None
    claims = verify_user_token(tok)
    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"


def test_user_auth_bad_password():
    assert authenticate_user("admin", "wrong") is None
    assert authenticate_user("nonexistent", "any") is None
