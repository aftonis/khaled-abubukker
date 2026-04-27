"""
FastAPI Backend - AIOps IoT Monitoring
========================================
REST endpoints:
  - /health                    health check
  - /auth/login                user login (returns JWT)
  - /devices                   CRUD on devices
  - /sensors/ingest            POST sensor readings (single or batch)
  - /sensors/readings          GET recent readings
  - /alerts                    GET alerts
  - /incidents                 GET incidents
  - /agents/logs               GET agent audit trail
  - /agents/run                POST trigger CrewAI pipeline
  - /ml/train                  POST train anomaly detector
  - /sim/seed                  POST seed simulator data
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.db.models import (
    init_db, get_db, Device, SensorReading, Alert, Incident, AgentTaskLog
)
from backend.api.schemas import (
    DeviceCreate, DeviceOut, SensorReadingIn, SensorReadingOut,
    AlertOut, IncidentOut, AgentLogOut, LoginRequest, TokenResponse,
    CrewRunRequest, CrewRunResponse,
)
from backend.auth.identity import authenticate_user, verify_user_token
from backend.simulator.sensor_sim import generate_devices, generate_batch
from backend.ml.anomaly_detector import AnomalyDetector

app = FastAPI(
    title="AIOps IoT Monitoring API",
    description="Secure IoT and Electronics Monitoring System with Agentic AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Auth dependency
# ============================================================

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.replace("Bearer ", "")
    claims = verify_user_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return claims


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# ============================================================
# Startup
# ============================================================

@app.on_event("startup")
def on_startup():
    init_db()


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "aiops-iot-monitoring",
    }


# ============================================================
# Auth
# ============================================================

@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    token = authenticate_user(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    claims = verify_user_token(token)
    return TokenResponse(access_token=token, role=claims.get("role", "operator"))


# ============================================================
# Devices
# ============================================================

@app.get("/devices", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.device_id).all()


@app.post("/devices", response_model=DeviceOut, status_code=201)
def create_device(d: DeviceCreate, db: Session = Depends(get_db)):
    if db.query(Device).filter(Device.device_id == d.device_id).first():
        raise HTTPException(status_code=409, detail=f"Device {d.device_id} already exists")
    device = Device(**d.dict())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@app.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)):
    d = db.query(Device).filter(Device.device_id == device_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    return d


# ============================================================
# Sensor Readings
# ============================================================

@app.post("/sensors/ingest", status_code=201)
def ingest_reading(reading: SensorReadingIn, db: Session = Depends(get_db)):
    """Ingest a single sensor reading. Updates device.last_seen and battery."""
    device = db.query(Device).filter(Device.device_id == reading.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail=f"Unknown device: {reading.device_id}")

    sr = SensorReading(
        device_id=reading.device_id,
        timestamp=datetime.utcnow(),
        temperature=reading.temperature,
        humidity=reading.humidity,
        vibration=reading.vibration,
        battery=reading.battery,
        signal_strength=reading.signal_strength,
    )
    db.add(sr)
    device.last_seen = datetime.utcnow()
    if reading.battery is not None:
        device.battery_level = reading.battery
    db.commit()
    db.refresh(sr)
    return {"id": sr.id, "ingested": True}


@app.post("/sensors/ingest/batch", status_code=201)
def ingest_batch(readings: List[SensorReadingIn], db: Session = Depends(get_db)):
    """Bulk ingest. More efficient for simulator/historical loads."""
    inserted = 0
    skipped = 0
    known_ids = {d.device_id for d in db.query(Device).all()}
    for r in readings:
        if r.device_id not in known_ids:
            skipped += 1
            continue
        sr = SensorReading(
            device_id=r.device_id,
            timestamp=datetime.utcnow(),
            temperature=r.temperature,
            humidity=r.humidity,
            vibration=r.vibration,
            battery=r.battery,
            signal_strength=r.signal_strength,
        )
        db.add(sr)
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped}


@app.get("/sensors/readings", response_model=List[SensorReadingOut])
def list_readings(
    device_id: Optional[str] = None,
    minutes: int = 60,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    q = db.query(SensorReading).filter(SensorReading.timestamp >= cutoff)
    if device_id:
        q = q.filter(SensorReading.device_id == device_id)
    return q.order_by(desc(SensorReading.timestamp)).limit(limit).all()


# ============================================================
# Alerts
# ============================================================

@app.get("/alerts", response_model=List[AlertOut])
def list_alerts(
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(Alert)
    if severity:
        q = q.filter(Alert.severity == severity.lower())
    if resolved is not None:
        q = q.filter(Alert.resolved == resolved)
    return q.order_by(desc(Alert.timestamp)).limit(limit).all()


@app.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    a.resolved = True
    db.commit()
    return {"resolved": True, "id": alert_id}


# ============================================================
# Incidents
# ============================================================

@app.get("/incidents", response_model=List[IncidentOut])
def list_incidents(
    classification: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(Incident)
    if classification:
        q = q.filter(Incident.classification == classification.lower())
    if status_filter:
        q = q.filter(Incident.status == status_filter.lower())
    return q.order_by(desc(Incident.detected_at)).limit(limit).all()


# ============================================================
# Agent Logs
# ============================================================

@app.get("/agents/logs", response_model=List[AgentLogOut])
def list_agent_logs(
    agent_name: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(AgentTaskLog)
    if agent_name:
        q = q.filter(AgentTaskLog.agent_name == agent_name)
    return q.order_by(desc(AgentTaskLog.timestamp)).limit(limit).all()


# ============================================================
# CrewAI Run
# ============================================================

@app.post("/agents/run", response_model=CrewRunResponse)
def run_agents(req: CrewRunRequest):
    """Trigger the 7-agent CrewAI pipeline. Requires Ollama to be running."""
    # Lazy import - CrewAI is heavy
    from backend.crew.crew import run_crew
    result = run_crew(user_request=req.user_request, verbose=req.verbose)
    return CrewRunResponse(**result)


# ============================================================
# ML Training
# ============================================================

@app.post("/ml/train")
def train_model(min_samples: int = 100, db: Session = Depends(get_db)):
    """Train the IsolationForest detector on all available readings."""
    readings = db.query(SensorReading).all()
    if len(readings) < min_samples:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {min_samples} readings, got {len(readings)}. Seed simulator first."
        )
    reading_dicts = [{
        "temperature": r.temperature or 0,
        "humidity": r.humidity or 0,
        "vibration": r.vibration or 0,
        "battery": r.battery or 0,
        "signal_strength": r.signal_strength or 0,
    } for r in readings]

    detector = AnomalyDetector(contamination=0.08)
    stats = detector.fit(reading_dicts)
    detector.save()
    return {"trained": True, **stats}


# ============================================================
# Simulator seeding
# ============================================================

@app.post("/sim/seed")
def seed_simulator(
    device_count: int = 12,
    readings_per_device: int = 100,
    anomaly_rate: float = 0.08,
    db: Session = Depends(get_db),
):
    """Seed the database with simulated devices + historical readings."""
    # Devices
    devices_data = generate_devices(device_count)
    new_devices = 0
    for d in devices_data:
        existing = db.query(Device).filter(Device.device_id == d["device_id"]).first()
        if not existing:
            db.add(Device(**d))
            new_devices += 1
    db.commit()

    # Readings
    all_devices = db.query(Device).all()
    devices_for_sim = [{
        "device_id": d.device_id, "location": d.location
    } for d in all_devices]

    readings = generate_batch(
        devices_for_sim,
        readings_per_device=readings_per_device,
        anomaly_rate=anomaly_rate,
    )
    for r in readings:
        sr = SensorReading(
            device_id=r["device_id"],
            timestamp=datetime.fromisoformat(r["timestamp"]),
            temperature=r["temperature"],
            humidity=r["humidity"],
            vibration=r["vibration"],
            battery=r["battery"],
            signal_strength=r["signal_strength"],
        )
        db.add(sr)
    db.commit()

    return {
        "new_devices": new_devices,
        "total_devices": len(all_devices),
        "readings_inserted": len(readings),
        "anomaly_rate": anomaly_rate,
    }


# ============================================================
# Stats / Analytics endpoint for dashboard
# ============================================================

@app.get("/stats/summary")
def stats_summary(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    return {
        "devices_total": db.query(Device).count(),
        "devices_active": db.query(Device).filter(Device.is_active == True).count(),
        "readings_24h": db.query(SensorReading).filter(SensorReading.timestamp >= last_24h).count(),
        "alerts_open": db.query(Alert).filter(Alert.resolved == False).count(),
        "alerts_critical": db.query(Alert).filter(
            Alert.resolved == False, Alert.severity == "critical"
        ).count(),
        "incidents_open": db.query(Incident).filter(Incident.status == "open").count(),
        "agent_runs_24h": db.query(AgentTaskLog).filter(
            AgentTaskLog.timestamp >= last_24h
        ).count(),
    }


# ============================================================
# QR Code endpoint
# ============================================================

@app.get("/devices/{device_id}/qr")
def device_qr(device_id: str, dashboard_url: str = "http://localhost:8501", db: Session = Depends(get_db)):
    """Return a QR code PNG for a device that links to its dashboard page."""
    from fastapi.responses import Response
    d = db.query(Device).filter(Device.device_id == device_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    from backend.outputs import generate_device_qr
    png_bytes = generate_device_qr(device_id, dashboard_url)
    return Response(content=png_bytes, media_type="image/png")


# ============================================================
# PDF incident report endpoint
# ============================================================

@app.get("/reports/incidents/pdf")
def download_incident_report(db: Session = Depends(get_db)):
    """Generate and download a full PDF incident report."""
    from fastapi.responses import Response
    from backend.outputs import generate_incident_report

    incidents = [
        {
            "device_id": i.device_id, "threat_type": i.threat_type,
            "classification": i.classification, "severity": i.severity,
            "status": i.status, "recommendation": i.recommendation,
            "detected_at": i.detected_at.isoformat(),
        }
        for i in db.query(Incident).order_by(desc(Incident.detected_at)).limit(100).all()
    ]
    alerts = [
        {"device_id": a.device_id, "severity": a.severity, "alert_type": a.alert_type}
        for a in db.query(Alert).order_by(desc(Alert.timestamp)).limit(200).all()
    ]
    logs = [
        {
            "agent_name": l.agent_name, "task": l.task,
            "validation_status": l.validation_status,
            "execution_time_ms": l.execution_time_ms,
        }
        for l in db.query(AgentTaskLog).order_by(desc(AgentTaskLog.timestamp)).limit(20).all()
    ]
    stats_data = {
        "devices_total": db.query(Device).count(),
        "readings_24h": db.query(SensorReading).filter(
            SensorReading.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count(),
        "agent_runs_24h": db.query(AgentTaskLog).filter(
            AgentTaskLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count(),
    }
    pdf_bytes = generate_incident_report(
        incidents, alerts, logs, stats_data,
        run_timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )
    filename = f"aiops_report_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=False,
    )
