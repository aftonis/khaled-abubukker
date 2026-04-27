"""
Anomaly Detection - IsolationForest
====================================
Lightweight, defensible anomaly detector for IoT telemetry.
Why IsolationForest:
  - Unsupervised (no labelled anomalies needed)
  - Fast on tabular data
  - Handles multivariate well (temp + humidity + vibration jointly)
  - Industry standard for this exact use case
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Tuple

MODEL_DIR = os.path.join(os.path.dirname(__file__), "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "iso_forest.joblib")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.joblib")

FEATURES = ["temperature", "humidity", "vibration", "battery", "signal_strength"]


class AnomalyDetector:
    """IsolationForest wrapper with scaling + persistence."""

    def __init__(self, contamination: float = 0.08, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.model: IsolationForest | None = None
        self.scaler: StandardScaler | None = None

    def fit(self, readings: List[Dict]) -> Dict:
        """Train on a list of reading dicts."""
        if len(readings) < 20:
            raise ValueError(f"Need at least 20 readings to train, got {len(readings)}")

        df = pd.DataFrame(readings)
        missing = [f for f in FEATURES if f not in df.columns]
        if missing:
            raise ValueError(f"Missing features in training data: {missing}")

        X = df[FEATURES].values
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )
        self.model.fit(X_scaled)

        # Self-evaluation on training set
        preds = self.model.predict(X_scaled)
        anomalies = (preds == -1).sum()

        return {
            "trained": True,
            "n_samples": len(readings),
            "n_features": len(FEATURES),
            "anomalies_detected": int(anomalies),
            "anomaly_rate": float(anomalies / len(readings)),
            "contamination": self.contamination,
        }

    def predict(self, reading: Dict) -> Tuple[bool, float]:
        """
        Predict if a single reading is anomalous.
        Returns: (is_anomaly: bool, anomaly_score: float in [-1, 1], lower = more anomalous)
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError("Model not trained. Call fit() or load() first.")

        X = np.array([[reading.get(f, 0.0) for f in FEATURES]])
        X_scaled = self.scaler.transform(X)
        pred = self.model.predict(X_scaled)[0]
        score = self.model.score_samples(X_scaled)[0]
        return bool(pred == -1), float(score)

    def predict_batch(self, readings: List[Dict]) -> List[Tuple[bool, float]]:
        """Vectorised prediction for many readings."""
        if self.model is None or self.scaler is None:
            raise RuntimeError("Model not trained.")
        df = pd.DataFrame(readings)
        X = df[FEATURES].values
        X_scaled = self.scaler.transform(X)
        preds = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        return [(p == -1, float(s)) for p, s in zip(preds, scores)]

    def save(self):
        """Persist model + scaler."""
        if self.model is None:
            raise RuntimeError("Nothing to save - model not trained")
        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)
        return {"model": MODEL_PATH, "scaler": SCALER_PATH}

    def load(self) -> bool:
        """Load persisted model + scaler. Returns True if successful."""
        if not (os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH)):
            return False
        self.model = joblib.load(MODEL_PATH)
        self.scaler = joblib.load(SCALER_PATH)
        return True


def classify_severity(score: float) -> str:
    """
    Map anomaly score to severity. Lower scores = more anomalous.
    Calibrated against IsolationForest output range (~-0.8 to -0.3 typical).
    """
    if score < -0.65:
        return "critical"
    elif score < -0.55:
        return "high"
    elif score < -0.45:
        return "medium"
    else:
        return "low"


def classify_alert_type(reading: Dict) -> str:
    """Heuristically classify what kind of anomaly based on which feature is extreme."""
    if reading.get("temperature", 20) > 35:
        return "temp_spike"
    if reading.get("temperature", 20) < 0:
        return "temp_drop"
    if reading.get("humidity", 50) > 85:
        return "humidity_flood"
    if reading.get("humidity", 50) < 15:
        return "humidity_drought"
    if reading.get("vibration", 1) > 8:
        return "vibration_spike"
    if reading.get("battery", 50) < 10:
        return "battery_critical"
    if reading.get("signal_strength", -65) < -90:
        return "signal_loss"
    return "multivariate_anomaly"


if __name__ == "__main__":
    # Smoke test
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from backend.simulator.sensor_sim import generate_devices, generate_batch

    print("[ML] Generating training data...")
    devices = generate_devices(10)
    readings = generate_batch(devices, readings_per_device=50, anomaly_rate=0.08)
    print(f"[ML] Got {len(readings)} readings")

    detector = AnomalyDetector(contamination=0.08)
    stats = detector.fit(readings)
    print(f"[ML] Training stats: {stats}")

    detector.save()
    print(f"[ML] Saved to {MODEL_PATH}")

    # Test single prediction
    test_normal = {"temperature": 21.0, "humidity": 50.0, "vibration": 1.0, "battery": 80.0, "signal_strength": -65.0}
    test_anomaly = {"temperature": 45.0, "humidity": 95.0, "vibration": 15.0, "battery": 5.0, "signal_strength": -95.0}

    is_anom, score = detector.predict(test_normal)
    print(f"[ML] Normal reading → anomaly={is_anom}, score={score:.3f}, severity={classify_severity(score)}")
    is_anom, score = detector.predict(test_anomaly)
    print(f"[ML] Extreme reading → anomaly={is_anom}, score={score:.3f}, severity={classify_severity(score)}")
