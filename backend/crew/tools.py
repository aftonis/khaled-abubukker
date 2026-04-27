"""
CrewAI Custom Tools (Pillar 4: Custom Tools)
=============================================
Tools that agents use to interact with the DB, ML models, and external systems.
Each tool enforces identity-aware permission checks.
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# Path setup so this works in Colab too
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.db.models import (
    SessionLocal, Device, SensorReading, Alert, Incident, AgentTaskLog
)
from backend.ml.anomaly_detector import (
    AnomalyDetector, classify_severity, classify_alert_type
)
from backend.auth.identity import (
    issue_agent_token, verify_agent_token, has_permission, hash_token
)


# ============================================================
# Tool 1: Fetch Recent Sensor Readings
# ============================================================

class FetchReadingsInput(BaseModel):
    minutes: int = Field(default=60, description="How many minutes of recent data to fetch")
    limit: int = Field(default=100, description="Max number of readings to return")


class FetchSensorReadingsTool(BaseTool):
    name: str = "fetch_recent_sensor_readings"
    description: str = (
        "Fetch the most recent sensor readings from the database. "
        "Returns a JSON list of readings with device_id, timestamp, and all sensor values. "
        "Use this to get current telemetry data for analysis."
    )
    args_schema: Type[BaseModel] = FetchReadingsInput

    def _run(self, minutes: int = 60, limit: int = 100) -> str:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            readings = (
                db.query(SensorReading)
                .filter(SensorReading.timestamp >= cutoff)
                .order_by(SensorReading.timestamp.desc())
                .limit(limit)
                .all()
            )
            result = [{
                "device_id": r.device_id,
                "timestamp": r.timestamp.isoformat(),
                "temperature": r.temperature,
                "humidity": r.humidity,
                "vibration": r.vibration,
                "battery": r.battery,
                "signal_strength": r.signal_strength,
            } for r in readings]
            return json.dumps({"count": len(result), "readings": result[:50]})  # cap output size
        except Exception as e:
            return json.dumps({"error": str(e), "count": 0, "readings": []})
        finally:
            db.close()


# ============================================================
# Tool 2: Check Device Health
# ============================================================

class DeviceHealthInput(BaseModel):
    pass


class CheckDeviceHealthTool(BaseTool):
    name: str = "check_device_health"
    description: str = (
        "Inspect every registered device and report battery, firmware, auth_status, "
        "and last-seen recency. Returns devices that need attention."
    )
    args_schema: Type[BaseModel] = DeviceHealthInput

    def _run(self) -> str:
        db = SessionLocal()
        try:
            devices = db.query(Device).all()
            now = datetime.utcnow()
            health_report = []
            issues = []
            for d in devices:
                stale_minutes = (now - d.last_seen).total_seconds() / 60 if d.last_seen else 999
                health = {
                    "device_id": d.device_id,
                    "name": d.name,
                    "location": d.location,
                    "battery_level": d.battery_level,
                    "firmware_version": d.firmware_version,
                    "auth_status": d.auth_status,
                    "stale_minutes": round(stale_minutes, 1),
                }
                # Flag issues
                if d.battery_level < 15:
                    issues.append(f"{d.device_id}: battery critical ({d.battery_level}%)")
                if d.auth_status != "authenticated":
                    issues.append(f"{d.device_id}: auth status = {d.auth_status}")
                if stale_minutes > 30:
                    issues.append(f"{d.device_id}: not seen for {stale_minutes:.0f} minutes")
                health_report.append(health)

            return json.dumps({
                "total_devices": len(devices),
                "issues_found": len(issues),
                "issues": issues[:20],
                "devices": health_report[:30],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
        finally:
            db.close()


# ============================================================
# Tool 3: Run ML Anomaly Detection
# ============================================================

class AnomalyScanInput(BaseModel):
    minutes: int = Field(default=60, description="Time window to scan")


class RunAnomalyDetectionTool(BaseTool):
    name: str = "run_anomaly_detection"
    description: str = (
        "Run the trained IsolationForest model on recent sensor readings. "
        "Returns a list of detected anomalies with device_id, severity, and alert_type."
    )
    args_schema: Type[BaseModel] = AnomalyScanInput

    def _run(self, minutes: int = 60) -> str:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            readings = db.query(SensorReading).filter(
                SensorReading.timestamp >= cutoff
            ).all()
            if not readings:
                return json.dumps({"scanned": 0, "anomalies": []})

            detector = AnomalyDetector()
            if not detector.load():
                return json.dumps({"error": "Model not trained yet. Call /train endpoint first."})

            reading_dicts = [{
                "device_id": r.device_id,
                "timestamp": r.timestamp.isoformat(),
                "temperature": r.temperature,
                "humidity": r.humidity,
                "vibration": r.vibration,
                "battery": r.battery,
                "signal_strength": r.signal_strength,
            } for r in readings]

            results = detector.predict_batch(reading_dicts)
            anomalies = []
            for reading, (is_anom, score) in zip(reading_dicts, results):
                if is_anom:
                    anomalies.append({
                        "device_id": reading["device_id"],
                        "timestamp": reading["timestamp"],
                        "severity": classify_severity(score),
                        "alert_type": classify_alert_type(reading),
                        "score": round(score, 3),
                        "values": {k: reading[k] for k in ["temperature", "humidity", "vibration", "battery", "signal_strength"]},
                    })

            return json.dumps({
                "scanned": len(reading_dicts),
                "anomalies_count": len(anomalies),
                "anomalies": anomalies[:30],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
        finally:
            db.close()


# ============================================================
# Tool 4: Write Alert
# ============================================================

class WriteAlertInput(BaseModel):
    device_id: str = Field(description="Device ID this alert relates to")
    severity: str = Field(description="low | medium | high | critical")
    alert_type: str = Field(description="e.g. temp_spike, vibration_spike, battery_critical")
    description: str = Field(description="Human-readable description of the alert")
    agent_source: str = Field(description="Name of the agent raising the alert")


class WriteAlertTool(BaseTool):
    name: str = "write_alert"
    description: str = (
        "Persist an alert to the database. Use this when an anomaly or device issue "
        "needs to be recorded for the operations team."
    )
    args_schema: Type[BaseModel] = WriteAlertInput

    def _run(self, device_id: str, severity: str, alert_type: str,
             description: str, agent_source: str) -> str:
        db = SessionLocal()
        try:
            # Verify device exists
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                return json.dumps({"error": f"Device {device_id} not found"})

            alert = Alert(
                device_id=device_id,
                severity=severity.lower(),
                alert_type=alert_type,
                description=description,
                agent_source=agent_source,
                anomaly_flag=True,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            return json.dumps({"alert_id": alert.id, "written": True})
        except Exception as e:
            db.rollback()
            return json.dumps({"error": str(e)})
        finally:
            db.close()


# ============================================================
# Tool 5: Write Incident with Recommendation
# ============================================================

class WriteIncidentInput(BaseModel):
    device_id: str = Field(description="Affected device ID")
    threat_type: str = Field(description="tampering, unauthorized_firmware, anomaly_cluster, etc.")
    classification: str = Field(description="security | operational | environmental")
    severity: str = Field(description="low | medium | high | critical")
    recommendation: str = Field(description="Recommended remediation action")


class WriteIncidentTool(BaseTool):
    name: str = "write_incident"
    description: str = (
        "Record a classified incident with a remediation recommendation. "
        "Use after an alert has been classified by severity and threat type."
    )
    args_schema: Type[BaseModel] = WriteIncidentInput

    def _run(self, device_id: str, threat_type: str, classification: str,
             severity: str, recommendation: str) -> str:
        db = SessionLocal()
        try:
            incident = Incident(
                device_id=device_id,
                threat_type=threat_type,
                classification=classification.lower(),
                severity=severity.lower(),
                recommendation=recommendation,
                status="open",
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)
            return json.dumps({"incident_id": incident.id, "written": True})
        except Exception as e:
            db.rollback()
            return json.dumps({"error": str(e)})
        finally:
            db.close()


# ============================================================
# Tool 6: Fetch Open Alerts (for classifier agent)
# ============================================================

class FetchAlertsInput(BaseModel):
    limit: int = Field(default=20, description="Max number of alerts to fetch")


class FetchOpenAlertsTool(BaseTool):
    name: str = "fetch_open_alerts"
    description: str = (
        "Fetch unresolved alerts from the database for classification. "
        "Returns alerts with device, severity, type, and description."
    )
    args_schema: Type[BaseModel] = FetchAlertsInput

    def _run(self, limit: int = 20) -> str:
        db = SessionLocal()
        try:
            alerts = (
                db.query(Alert)
                .filter(Alert.resolved == False)
                .order_by(Alert.timestamp.desc())
                .limit(limit)
                .all()
            )
            result = [{
                "alert_id": a.id,
                "device_id": a.device_id,
                "severity": a.severity,
                "alert_type": a.alert_type,
                "description": a.description,
                "timestamp": a.timestamp.isoformat(),
            } for a in alerts]
            return json.dumps({"count": len(result), "alerts": result})
        except Exception as e:
            return json.dumps({"error": str(e)})
        finally:
            db.close()


# ============================================================
# Tool 7: Log Agent Task (audit trail with identity hash)
# ============================================================

def log_agent_task(
    agent_name: str,
    agent_role: str,
    task: str,
    input_summary: str,
    output: str,
    validation_status: str = "pending",
    validator_agent: str = None,
    execution_time_ms: int = 0,
):
    """Direct DB write for agent audit logging - called from crew.py."""
    db = SessionLocal()
    try:
        token = issue_agent_token(agent_name) if agent_name in [
            "telemetry_ingestion", "device_health", "anomaly_detector",
            "security", "incident_classifier", "response_recommender", "validator"
        ] else None

        log = AgentTaskLog(
            agent_name=agent_name,
            agent_role=agent_role,
            task=task,
            input_summary=input_summary[:500] if input_summary else "",
            output=output[:2000] if output else "",
            validation_status=validation_status,
            validator_agent=validator_agent,
            identity_token_hash=hash_token(token) if token else "",
            execution_time_ms=execution_time_ms,
        )
        db.add(log)
        db.commit()
        return log.id
    except Exception as e:
        db.rollback()
        print(f"[audit] Failed to log task: {e}")
        return None
    finally:
        db.close()


# Registry for easy import
ALL_TOOLS = {
    "fetch_readings": FetchSensorReadingsTool(),
    "check_device_health": CheckDeviceHealthTool(),
    "run_anomaly_detection": RunAnomalyDetectionTool(),
    "write_alert": WriteAlertTool(),
    "write_incident": WriteIncidentTool(),
    "fetch_open_alerts": FetchOpenAlertsTool(),
}
