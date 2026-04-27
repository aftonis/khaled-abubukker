"""
Database Schema - AIOps IoT Monitoring
=======================================
5 tables matching the assignment specification:
1. devices - IoT device registry
2. sensor_readings - environmental telemetry
3. alerts - anomaly flags + maintenance recommendations
4. incidents - classified threats with response recommendations
5. agent_task_logs - identity-aware agent decision audit trail
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aiops_iot.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Device(Base):
    """IoT device registry - sensors deployed in warehouse."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(100), nullable=False)  # e.g., "Warehouse-A-Zone-3"
    device_type = Column(String(50), nullable=False)  # temp_sensor, humidity_sensor, vibration_sensor
    firmware_version = Column(String(20), nullable=False)
    auth_status = Column(String(20), default="authenticated")  # authenticated, unauthorized, suspicious
    battery_level = Column(Float, default=100.0)
    is_active = Column(Boolean, default=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    readings = relationship("SensorReading", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="device", cascade="all, delete-orphan")


class SensorReading(Base):
    """Environmental telemetry from devices."""
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("devices.device_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    temperature = Column(Float)  # Celsius
    humidity = Column(Float)     # %
    vibration = Column(Float)    # mm/s RMS
    battery = Column(Float)      # %
    signal_strength = Column(Float)  # dBm

    device = relationship("Device", back_populates="readings")


class Alert(Base):
    """Anomaly flags raised by detection agents."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("devices.device_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    anomaly_flag = Column(Boolean, default=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    alert_type = Column(String(50), nullable=False)  # temp_anomaly, vibration_spike, battery_low, etc.
    description = Column(Text)
    agent_source = Column(String(50))  # which agent raised it
    resolved = Column(Boolean, default=False)

    device = relationship("Device", back_populates="alerts")


class Incident(Base):
    """Classified security/operational incidents with response recommendations."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("devices.device_id"), nullable=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    threat_type = Column(String(50), nullable=False)  # tampering, unauthorized_firmware, anomaly_cluster
    classification = Column(String(20), nullable=False)  # security, operational, environmental
    severity = Column(String(20), nullable=False)
    status = Column(String(20), default="open")  # open, investigating, resolved, false_positive
    recommendation = Column(Text)  # Response action recommended by agent
    resolved_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="incidents")


class AgentTaskLog(Base):
    """Identity-aware agent audit trail - every decision is logged & validated."""
    __tablename__ = "agent_task_logs"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(50), nullable=False, index=True)
    agent_role = Column(String(100), nullable=False)
    task = Column(String(100), nullable=False)
    input_summary = Column(Text)
    output = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    validation_status = Column(String(20), default="pending")  # pending, validated, rejected
    validator_agent = Column(String(50), nullable=True)
    identity_token_hash = Column(String(64))  # hash of signing token (never store raw)
    execution_time_ms = Column(Integer, default=0)


# --- DB utilities ---

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db():
    """Drop and recreate all tables - for tests/demos."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print(f"Database ready at: {DATABASE_URL}")
