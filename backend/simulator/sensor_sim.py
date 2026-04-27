"""
IoT Sensor Simulator
=====================
Simulates a warehouse environment with multiple IoT devices generating
temperature, humidity, vibration, battery, and signal-strength readings.

Includes deliberate anomaly injection (~8% by default) for ML training/demo.
"""

import random
import math
from datetime import datetime, timedelta
from typing import List, Dict
import os


# Realistic warehouse zones
WAREHOUSE_ZONES = [
    "Warehouse-A-Zone-1", "Warehouse-A-Zone-2", "Warehouse-A-Zone-3",
    "Warehouse-B-Cold-Storage", "Warehouse-B-Receiving",
    "Warehouse-C-Loading-Bay", "Warehouse-C-Office",
]

DEVICE_TYPES = ["temp_sensor", "humidity_sensor", "vibration_sensor", "multi_sensor"]
FIRMWARE_VERSIONS = ["1.2.3", "1.2.4", "1.3.0", "1.3.1", "2.0.0"]


def generate_devices(count: int = 12) -> List[Dict]:
    """Generate a fixed roster of IoT devices."""
    devices = []
    for i in range(count):
        device = {
            "device_id": f"IOT-{1000 + i:04d}",
            "name": f"Sensor-{chr(65 + (i % 26))}{i:02d}",
            "location": random.choice(WAREHOUSE_ZONES),
            "device_type": random.choice(DEVICE_TYPES),
            "firmware_version": random.choice(FIRMWARE_VERSIONS),
            "auth_status": "authenticated",
            "battery_level": round(random.uniform(45.0, 100.0), 1),
        }
        devices.append(device)
    return devices


def generate_reading(
    device_id: str,
    location: str,
    inject_anomaly: bool = False,
    timestamp: datetime = None
) -> Dict:
    """
    Generate a single sensor reading.

    Normal ranges (warehouse):
      - temperature: 18-24 C (cold storage: 2-8 C)
      - humidity: 40-60 %
      - vibration: 0.1-2.0 mm/s
      - battery: drains slowly
      - signal: -50 to -75 dBm (good)

    Anomalies:
      - temperature spike (>35 or <0)
      - humidity flood (>85 or <15)
      - vibration spike (tampering, equipment failure)
      - signal drop (-90+ dBm)
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    is_cold_storage = "Cold-Storage" in location

    # Baseline readings
    temp_baseline = random.uniform(2, 8) if is_cold_storage else random.uniform(18, 24)
    humidity_baseline = random.uniform(40, 60)
    vibration_baseline = random.uniform(0.1, 2.0)
    signal_baseline = random.uniform(-75, -50)
    battery_baseline = random.uniform(40, 100)

    if inject_anomaly:
        anomaly_type = random.choice([
            "temp_spike", "temp_drop", "humidity_flood", "vibration_spike",
            "signal_drop", "battery_critical"
        ])
        if anomaly_type == "temp_spike":
            temp_baseline = random.uniform(35, 50)
        elif anomaly_type == "temp_drop":
            temp_baseline = random.uniform(-10, 0)
        elif anomaly_type == "humidity_flood":
            humidity_baseline = random.uniform(85, 99)
        elif anomaly_type == "vibration_spike":
            vibration_baseline = random.uniform(8, 20)
        elif anomaly_type == "signal_drop":
            signal_baseline = random.uniform(-100, -90)
        elif anomaly_type == "battery_critical":
            battery_baseline = random.uniform(1, 10)

    # Add small noise
    return {
        "device_id": device_id,
        "timestamp": timestamp.isoformat(),
        "temperature": round(temp_baseline + random.gauss(0, 0.3), 2),
        "humidity": round(humidity_baseline + random.gauss(0, 1.0), 2),
        "vibration": round(max(0, vibration_baseline + random.gauss(0, 0.1)), 3),
        "battery": round(max(0, min(100, battery_baseline)), 1),
        "signal_strength": round(signal_baseline + random.gauss(0, 2), 1),
    }


def generate_batch(
    devices: List[Dict],
    readings_per_device: int = 50,
    anomaly_rate: float = 0.08,
    time_window_hours: int = 24,
) -> List[Dict]:
    """
    Generate historical batch of readings across all devices over a time window.
    Useful for seeding demo data.
    """
    readings = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=time_window_hours)
    interval_seconds = (time_window_hours * 3600) / max(readings_per_device, 1)

    for device in devices:
        for i in range(readings_per_device):
            ts = start_time + timedelta(seconds=i * interval_seconds)
            inject = random.random() < anomaly_rate
            reading = generate_reading(
                device_id=device["device_id"],
                location=device["location"],
                inject_anomaly=inject,
                timestamp=ts,
            )
            readings.append(reading)

    return readings


def simulate_security_event(device: Dict) -> Dict:
    """Generate a security-relevant event (tampering, unauthorized firmware, auth fail)."""
    events = [
        {
            "type": "unauthorized_firmware",
            "details": f"Device {device['device_id']} reporting firmware version 0.0.1 (unsigned)",
            "auth_status": "suspicious",
        },
        {
            "type": "auth_failure",
            "details": f"Device {device['device_id']} failed mutual TLS handshake 5 times",
            "auth_status": "unauthorized",
        },
        {
            "type": "tampering_suspected",
            "details": f"Device {device['device_id']} physical seal sensor triggered",
            "auth_status": "suspicious",
        },
    ]
    return random.choice(events)


if __name__ == "__main__":
    # Quick smoke test
    devices = generate_devices(5)
    print(f"Generated {len(devices)} devices")
    print("Sample device:", devices[0])

    readings = generate_batch(devices, readings_per_device=10, anomaly_rate=0.2)
    print(f"\nGenerated {len(readings)} readings")
    print("Sample reading:", readings[0])
