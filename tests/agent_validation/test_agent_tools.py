"""
Agent Behaviour Validation Tests
=================================
Validates agent TOOLS work correctly without invoking the LLM.
The LLM-driven crew run is tested separately in a Colab demo.
"""
import json
from datetime import datetime
from backend.crew.tools import (
    FetchSensorReadingsTool, CheckDeviceHealthTool, RunAnomalyDetectionTool,
    WriteAlertTool, WriteIncidentTool, FetchOpenAlertsTool, log_agent_task,
)
from backend.db.models import Device, SensorReading, Alert, Incident, AgentTaskLog
from backend.simulator.sensor_sim import generate_devices, generate_batch
from backend.ml.anomaly_detector import AnomalyDetector


def _seed(db_session, n_devices=5, readings_per_device=30):
    """Seed fixture data."""
    devices = generate_devices(n_devices)
    for d in devices:
        db_session.add(Device(**d))
    db_session.commit()
    devs = db_session.query(Device).all()
    sim_devs = [{"device_id": d.device_id, "location": d.location} for d in devs]
    readings = generate_batch(sim_devs, readings_per_device=readings_per_device, anomaly_rate=0.1)
    for r in readings:
        db_session.add(SensorReading(
            device_id=r["device_id"],
            timestamp=datetime.fromisoformat(r["timestamp"]),
            temperature=r["temperature"], humidity=r["humidity"],
            vibration=r["vibration"], battery=r["battery"],
            signal_strength=r["signal_strength"],
        ))
    db_session.commit()
    return devs


def test_fetch_readings_tool(db_session, monkeypatch):
    # Make tool use the test DB session
    from backend.crew import tools as tools_mod
    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)

    _seed(db_session)
    tool = FetchSensorReadingsTool()
    result = json.loads(tool._run(minutes=99999, limit=50))
    assert "readings" in result
    assert result["count"] > 0


def test_check_device_health_tool(db_session, monkeypatch):
    from backend.crew import tools as tools_mod
    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)

    devs = _seed(db_session, n_devices=4)
    # Force one device to have low battery
    devs[0].battery_level = 5.0
    db_session.commit()

    tool = CheckDeviceHealthTool()
    result = json.loads(tool._run())
    assert result["total_devices"] == 4
    assert any("battery critical" in i for i in result["issues"])


def test_write_alert_tool(db_session, monkeypatch):
    from backend.crew import tools as tools_mod
    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)

    _seed(db_session, n_devices=3, readings_per_device=5)
    devs = db_session.query(Device).all()

    tool = WriteAlertTool()
    result = json.loads(tool._run(
        device_id=devs[0].device_id,
        severity="high",
        alert_type="temp_spike",
        description="Test alert",
        agent_source="test_agent",
    ))
    assert result.get("written") is True
    assert "alert_id" in result

    # Verify it actually got written
    alerts = db_session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].severity == "high"


def test_write_alert_unknown_device(db_session, monkeypatch):
    from backend.crew import tools as tools_mod
    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)

    tool = WriteAlertTool()
    result = json.loads(tool._run(
        device_id="IOT-NOPE",
        severity="high", alert_type="x", description="d", agent_source="t",
    ))
    assert "error" in result


def test_write_incident_tool(db_session, monkeypatch):
    from backend.crew import tools as tools_mod
    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)

    _seed(db_session, n_devices=3, readings_per_device=5)
    devs = db_session.query(Device).all()

    tool = WriteIncidentTool()
    result = json.loads(tool._run(
        device_id=devs[0].device_id,
        threat_type="tampering",
        classification="security",
        severity="critical",
        recommendation="Quarantine device",
    ))
    assert result.get("written") is True

    incidents = db_session.query(Incident).all()
    assert len(incidents) == 1
    assert incidents[0].classification == "security"


def test_run_anomaly_detection_no_model(db_session, monkeypatch, tmp_path):
    """If model not trained, tool should report error gracefully."""
    from backend.crew import tools as tools_mod
    from backend.ml import anomaly_detector as ml_mod

    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)
    # Point model dir to empty tmp dir → no saved model
    monkeypatch.setattr(ml_mod, "MODEL_PATH", str(tmp_path / "iso.joblib"))
    monkeypatch.setattr(ml_mod, "SCALER_PATH", str(tmp_path / "scaler.joblib"))

    _seed(db_session, n_devices=3, readings_per_device=10)
    tool = RunAnomalyDetectionTool()
    result = json.loads(tool._run(minutes=99999))
    assert "error" in result


def test_log_agent_task(db_session, monkeypatch):
    from backend.crew import tools as tools_mod
    monkeypatch.setattr(tools_mod, "SessionLocal", lambda: db_session)

    log_id = log_agent_task(
        agent_name="device_health",
        agent_role="Device Health Monitor",
        task="test_task",
        input_summary="test input",
        output="test output",
        validation_status="validated",
        execution_time_ms=42,
    )
    assert log_id is not None
    log = db_session.query(AgentTaskLog).first()
    assert log.agent_name == "device_health"
    assert log.execution_time_ms == 42
    assert len(log.identity_token_hash) == 64  # SHA-256 hex
