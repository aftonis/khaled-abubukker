"""Integration tests - FastAPI end-to-end flows."""
import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_admin(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    assert "access_token" in r.json()


def test_login_bad_credentials(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_seed_devices_and_readings(client):
    r = client.post("/sim/seed", params={
        "device_count": 5, "readings_per_device": 30, "anomaly_rate": 0.1
    })
    assert r.status_code == 200
    body = r.json()
    assert body["new_devices"] == 5
    assert body["readings_inserted"] == 150


def test_list_devices_after_seed(client):
    client.post("/sim/seed", params={"device_count": 8, "readings_per_device": 10})
    r = client.get("/devices")
    assert r.status_code == 200
    assert len(r.json()) >= 8


def test_get_specific_device(client):
    client.post("/sim/seed", params={"device_count": 5, "readings_per_device": 5})
    devices = client.get("/devices").json()
    device_id = devices[0]["device_id"]
    r = client.get(f"/devices/{device_id}")
    assert r.status_code == 200
    assert r.json()["device_id"] == device_id


def test_get_nonexistent_device(client):
    r = client.get("/devices/IOT-NOPE-9999")
    assert r.status_code == 404


def test_create_device(client):
    r = client.post("/devices", json={
        "device_id": "IOT-CUSTOM-1",
        "name": "Custom",
        "location": "Test-Zone",
        "device_type": "multi_sensor",
        "firmware_version": "1.0.0",
    })
    assert r.status_code == 201
    assert r.json()["device_id"] == "IOT-CUSTOM-1"


def test_duplicate_device_rejected(client):
    client.post("/devices", json={
        "device_id": "IOT-DUP", "name": "n", "location": "z",
        "device_type": "temp_sensor", "firmware_version": "1.0",
    })
    r = client.post("/devices", json={
        "device_id": "IOT-DUP", "name": "n2", "location": "z2",
        "device_type": "temp_sensor", "firmware_version": "1.0",
    })
    assert r.status_code == 409


def test_ingest_single_reading(client):
    client.post("/devices", json={
        "device_id": "IOT-ING-1", "name": "n", "location": "z",
        "device_type": "temp_sensor", "firmware_version": "1.0",
    })
    r = client.post("/sensors/ingest", json={
        "device_id": "IOT-ING-1",
        "temperature": 22.5, "humidity": 50.0, "vibration": 1.0,
        "battery": 90.0, "signal_strength": -65.0,
    })
    assert r.status_code == 201
    assert r.json()["ingested"] is True


def test_ingest_unknown_device(client):
    r = client.post("/sensors/ingest", json={
        "device_id": "IOT-NOPE-9999",
        "temperature": 22.5,
    })
    assert r.status_code == 404


def test_train_model_insufficient_data(client):
    client.post("/sim/seed", params={"device_count": 2, "readings_per_device": 2})
    r = client.post("/ml/train", params={"min_samples": 100})
    assert r.status_code == 400


def test_train_model_success(client):
    client.post("/sim/seed", params={"device_count": 5, "readings_per_device": 30})
    r = client.post("/ml/train", params={"min_samples": 50})
    assert r.status_code == 200
    assert r.json()["trained"] is True


def test_stats_summary(client):
    client.post("/sim/seed", params={"device_count": 3, "readings_per_device": 10})
    r = client.get("/stats/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["devices_total"] == 3
    # readings_24h may vary slightly due to timestamp simulation window — just check > 0
    assert body["readings_24h"] > 0


def test_alerts_endpoint_empty(client):
    r = client.get("/alerts")
    assert r.status_code == 200
    assert r.json() == []


def test_incidents_endpoint_empty(client):
    r = client.get("/incidents")
    assert r.status_code == 200
    assert r.json() == []


def test_agent_logs_empty(client):
    r = client.get("/agents/logs")
    assert r.status_code == 200
    assert r.json() == []
