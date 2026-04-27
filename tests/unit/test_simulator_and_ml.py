"""Unit tests for the IoT simulator and ML detector."""
import pytest
from backend.simulator.sensor_sim import (
    generate_devices, generate_reading, generate_batch, simulate_security_event
)
from backend.ml.anomaly_detector import (
    AnomalyDetector, classify_severity, classify_alert_type
)


def test_generate_devices_count():
    devices = generate_devices(15)
    assert len(devices) == 15
    assert all("device_id" in d for d in devices)
    assert all("location" in d for d in devices)


def test_generate_devices_unique_ids():
    devices = generate_devices(20)
    ids = [d["device_id"] for d in devices]
    assert len(ids) == len(set(ids))


def test_generate_normal_reading():
    r = generate_reading("IOT-X", "Warehouse-A-Zone-1", inject_anomaly=False)
    assert 15 < r["temperature"] < 28
    assert 30 < r["humidity"] < 70
    assert 0 <= r["vibration"] < 3


def test_generate_anomaly_reading():
    # Run several to ensure at least some hit out-of-range values
    extreme_count = 0
    for _ in range(20):
        r = generate_reading("IOT-X", "Warehouse-A-Zone-1", inject_anomaly=True)
        if (r["temperature"] > 30 or r["temperature"] < 5
            or r["humidity"] > 80 or r["vibration"] > 7
            or r["battery"] < 15 or r["signal_strength"] < -85):
            extreme_count += 1
    assert extreme_count > 10  # most anomaly injections produce extreme values


def test_generate_batch_size():
    devices = generate_devices(5)
    readings = generate_batch(devices, readings_per_device=20, anomaly_rate=0.1)
    assert len(readings) == 100


def test_security_event():
    e = simulate_security_event({"device_id": "IOT-X"})
    assert "type" in e
    assert e["type"] in ["unauthorized_firmware", "auth_failure", "tampering_suspected"]


def test_anomaly_detector_train_predict():
    devices = generate_devices(8)
    readings = generate_batch(devices, readings_per_device=100, anomaly_rate=0.05)
    det = AnomalyDetector(contamination=0.05)
    stats = det.fit(readings)
    assert stats["trained"] is True
    assert stats["n_samples"] == 800

    # Normal reading should usually not be flagged
    normal = {"temperature": 21, "humidity": 50, "vibration": 1.0,
              "battery": 80, "signal_strength": -65}
    is_anom_normal, _ = det.predict(normal)

    # Extreme reading should be flagged
    extreme = {"temperature": 50, "humidity": 99, "vibration": 20,
               "battery": 2, "signal_strength": -100}
    is_anom_extreme, score_extreme = det.predict(extreme)
    assert bool(is_anom_extreme) is True
    assert score_extreme < -0.4  # very anomalous


def test_anomaly_detector_insufficient_data():
    det = AnomalyDetector()
    with pytest.raises(ValueError):
        det.fit([{"temperature": 20, "humidity": 50, "vibration": 1, "battery": 80, "signal_strength": -65}])


def test_classify_severity():
    assert classify_severity(-0.7) == "critical"
    assert classify_severity(-0.6) == "high"
    assert classify_severity(-0.5) == "medium"
    assert classify_severity(-0.4) == "low"


def test_classify_alert_type():
    assert classify_alert_type({"temperature": 50, "humidity": 50, "vibration": 1, "battery": 80, "signal_strength": -65}) == "temp_spike"
    assert classify_alert_type({"temperature": -5, "humidity": 50, "vibration": 1, "battery": 80, "signal_strength": -65}) == "temp_drop"
    assert classify_alert_type({"temperature": 20, "humidity": 90, "vibration": 1, "battery": 80, "signal_strength": -65}) == "humidity_flood"
    assert classify_alert_type({"temperature": 20, "humidity": 50, "vibration": 15, "battery": 80, "signal_strength": -65}) == "vibration_spike"
    assert classify_alert_type({"temperature": 20, "humidity": 50, "vibration": 1, "battery": 5, "signal_strength": -65}) == "battery_critical"
