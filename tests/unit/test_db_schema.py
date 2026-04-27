"""Unit tests for the database schema."""
from datetime import datetime
from backend.db.models import Device, SensorReading, Alert, Incident, AgentTaskLog


def test_device_create(db_session):
    d = Device(
        device_id="IOT-TEST-1",
        name="Test Sensor",
        location="Test-Zone",
        device_type="temp_sensor",
        firmware_version="1.0.0",
    )
    db_session.add(d)
    db_session.commit()
    assert d.id is not None
    assert d.auth_status == "authenticated"


def test_sensor_reading_create(db_session):
    d = Device(device_id="IOT-T2", name="t", location="z", device_type="temp_sensor", firmware_version="1.0")
    db_session.add(d); db_session.commit()
    r = SensorReading(
        device_id="IOT-T2",
        temperature=21.5, humidity=50.0, vibration=1.0, battery=80.0, signal_strength=-65,
    )
    db_session.add(r); db_session.commit()
    assert r.id is not None
    assert r.timestamp is not None


def test_alert_create(db_session):
    d = Device(device_id="IOT-T3", name="t", location="z", device_type="temp_sensor", firmware_version="1.0")
    db_session.add(d); db_session.commit()
    a = Alert(
        device_id="IOT-T3", severity="high",
        alert_type="temp_spike", description="test",
        agent_source="anomaly_detector",
    )
    db_session.add(a); db_session.commit()
    assert a.resolved is False
    assert a.severity == "high"


def test_incident_create(db_session):
    d = Device(device_id="IOT-T4", name="t", location="z", device_type="temp_sensor", firmware_version="1.0")
    db_session.add(d); db_session.commit()
    i = Incident(
        device_id="IOT-T4", threat_type="tampering",
        classification="security", severity="critical",
        recommendation="Quarantine",
    )
    db_session.add(i); db_session.commit()
    assert i.status == "open"


def test_agent_log_create(db_session):
    log = AgentTaskLog(
        agent_name="device_health",
        agent_role="Device Health Monitor",
        task="health_check",
        input_summary="test",
        output="ok",
        validation_status="validated",
        identity_token_hash="abc123",
    )
    db_session.add(log); db_session.commit()
    assert log.id is not None
