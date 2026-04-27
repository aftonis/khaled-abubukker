"""API request/response schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# --- Devices ---
class DeviceCreate(BaseModel):
    device_id: str
    name: str
    location: str
    device_type: str
    firmware_version: str
    battery_level: float = 100.0


class DeviceOut(BaseModel):
    id: int
    device_id: str
    name: str
    location: str
    device_type: str
    firmware_version: str
    auth_status: str
    battery_level: float
    is_active: bool
    last_seen: datetime

    class Config:
        from_attributes = True


# --- Sensor readings ---
class SensorReadingIn(BaseModel):
    device_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    vibration: Optional[float] = None
    battery: Optional[float] = None
    signal_strength: Optional[float] = None


class SensorReadingOut(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    temperature: Optional[float]
    humidity: Optional[float]
    vibration: Optional[float]
    battery: Optional[float]
    signal_strength: Optional[float]

    class Config:
        from_attributes = True


# --- Alerts ---
class AlertOut(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    severity: str
    alert_type: str
    description: Optional[str]
    agent_source: Optional[str]
    resolved: bool

    class Config:
        from_attributes = True


# --- Incidents ---
class IncidentOut(BaseModel):
    id: int
    device_id: str
    detected_at: datetime
    threat_type: str
    classification: str
    severity: str
    status: str
    recommendation: Optional[str]

    class Config:
        from_attributes = True


# --- Agent logs ---
class AgentLogOut(BaseModel):
    id: int
    agent_name: str
    agent_role: str
    task: str
    input_summary: Optional[str]
    output: Optional[str]
    timestamp: datetime
    validation_status: str
    execution_time_ms: int

    class Config:
        from_attributes = True


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# --- Crew run ---
class CrewRunRequest(BaseModel):
    user_request: str = "Run the standard AIOps pipeline"
    verbose: bool = False


class CrewRunResponse(BaseModel):
    status: str
    execution_time_ms: int
    agents_run: Optional[int] = None
    final_output: Optional[str] = None
    error: Optional[str] = None
    timestamp: str
