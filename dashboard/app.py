"""
AIOps IoT Monitoring Dashboard
================================
Full 7-page Streamlit dashboard:
  1. Overview         - KPIs and health summary
  2. Devices          - device fleet management
  3. Sensors          - real-time telemetry charts
  4. Alerts           - active and resolved alerts
  5. Incidents        - classified incidents + recommendations
  6. Agent Logs       - identity-aware audit trail
  7. Analytics        - trends, distributions, anomaly patterns
  8. Admin / Auth     - login, system controls (train, seed, run crew)
"""

import os
import random
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

API_BASE = os.getenv("STREAMLIT_API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="AIOps IoT Monitor",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Session state init
# ============================================================
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "username" not in st.session_state:
    st.session_state.username = None
if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = False


# ============================================================
# Mock data — realistic warehouse IoT fleet (fixed seed)
# ============================================================
def _mock_devices():
    rng = random.Random(42)
    locations = ["Warehouse-A", "Warehouse-B", "Server-Room", "Loading-Bay", "Cold-Storage"]
    types = ["temperature_sensor", "vibration_sensor", "humidity_sensor", "motion_sensor", "gateway"]
    auth_states = ["authenticated", "authenticated", "authenticated", "suspicious", "unauthorized"]
    devices = []
    for i in range(1, 21):
        devices.append({
            "device_id": f"DEV-{i:03d}",
            "device_type": rng.choice(types),
            "location": rng.choice(locations),
            "is_active": rng.random() > 0.1,
            "battery_level": rng.randint(5, 100),
            "firmware_version": f"2.{rng.randint(0,3)}.{rng.randint(0,9)}",
            "auth_status": rng.choice(auth_states),
            "registered_at": (datetime.utcnow() - timedelta(days=rng.randint(1, 180))).isoformat(),
        })
    return devices


def _mock_readings(minutes=60, limit=500, device_id=None):
    rng = np.random.default_rng(42)
    devices = _mock_devices()
    if device_id:
        devices = [d for d in devices if d["device_id"] == device_id] or devices[:3]
    now = datetime.utcnow()
    rows = []
    count = min(limit, 500)
    for i in range(count):
        dev = devices[i % len(devices)]
        ts = now - timedelta(minutes=rng.integers(0, minutes))
        temp = float(rng.normal(22, 4))
        rows.append({
            "id": i + 1,
            "device_id": dev["device_id"],
            "timestamp": ts.isoformat(),
            "temperature": round(temp, 2),
            "humidity": round(float(rng.normal(55, 10)), 2),
            "vibration": round(float(abs(rng.normal(0.3, 0.2))), 3),
            "battery": round(float(rng.uniform(10, 100)), 1),
            "signal_strength": round(float(rng.uniform(-90, -40)), 1),
            "is_anomaly": bool(rng.random() < 0.08),
        })
    return rows


def _mock_alerts():
    rng = random.Random(99)
    devices = _mock_devices()
    severities = ["critical", "high", "medium", "low"]
    types = ["temperature_spike", "battery_critical", "vibration_anomaly",
             "auth_failure", "offline_device", "humidity_out_of_range"]
    agents = ["anomaly_detector", "security", "device_health"]
    alerts = []
    for i in range(30):
        dev = rng.choice(devices)
        sev = rng.choices(severities, weights=[1, 3, 5, 6])[0]
        alerts.append({
            "id": i + 1,
            "timestamp": (datetime.utcnow() - timedelta(hours=rng.randint(0, 48))).isoformat(),
            "device_id": dev["device_id"],
            "severity": sev,
            "alert_type": rng.choice(types),
            "agent_source": rng.choice(agents),
            "resolved": rng.random() > 0.4,
            "message": f"Anomaly detected on {dev['device_id']} in {dev['location']}",
        })
    return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)


def _mock_incidents():
    rng = random.Random(7)
    devices = _mock_devices()
    classifications = ["security", "operational", "environmental"]
    threat_types = ["unauthorized_access", "sensor_failure", "battery_depletion",
                    "temperature_critical", "network_anomaly"]
    statuses = ["open", "investigating", "resolved", "false_positive"]
    recommendations = [
        "Isolate device and rotate authentication credentials immediately.",
        "Schedule preventive maintenance within 48 hours.",
        "Replace battery unit; escalate to facilities team.",
        "Activate cooling protocol; alert site supervisor.",
        "Review network access logs and apply firewall rule.",
    ]
    incidents = []
    for i in range(15):
        dev = rng.choice(devices)
        incidents.append({
            "id": i + 1,
            "detected_at": (datetime.utcnow() - timedelta(hours=rng.randint(1, 72))).isoformat(),
            "device_id": dev["device_id"],
            "threat_type": rng.choice(threat_types),
            "classification": rng.choice(classifications),
            "severity": rng.choice(["critical", "high", "medium", "low"]),
            "status": rng.choice(statuses),
            "recommendation": rng.choice(recommendations),
        })
    return incidents


def _mock_agent_logs():
    rng = random.Random(13)
    agents = ["telemetry_ingestion", "device_health", "anomaly_detector",
              "security", "incident_classifier", "response_recommender", "validator"]
    tasks = ["Process sensor batch", "Evaluate device health", "Score anomaly risk",
             "Audit auth events", "Classify incident", "Generate recommendation", "Validate outputs"]
    statuses = ["validated", "validated", "validated", "pending", "rejected"]
    logs = []
    for i in range(40):
        agent = rng.choice(agents)
        logs.append({
            "id": i + 1,
            "timestamp": (datetime.utcnow() - timedelta(minutes=rng.randint(0, 360))).isoformat(),
            "agent_name": agent,
            "agent_role": agent.replace("_", " ").title(),
            "task": rng.choice(tasks),
            "validation_status": rng.choice(statuses),
            "execution_time_ms": rng.randint(120, 4500),
            "input_summary": f"Processed {rng.randint(5, 50)} records from {rng.randint(1, 5)} devices",
            "output": f"[{agent.upper()}] Task completed. {rng.randint(0, 5)} anomalies flagged.",
        })
    return sorted(logs, key=lambda x: x["timestamp"], reverse=True)


def _mock_summary():
    return {
        "devices_total": 20,
        "devices_active": 18,
        "readings_24h": 14400,
        "agent_runs_24h": 6,
        "alerts_open": 12,
        "alerts_critical": 3,
        "incidents_open": 5,
    }


MOCK_DATA = {
    "/health": {"status": "ok", "mode": "demo"},
    "/stats/summary": _mock_summary(),
    "/devices": _mock_devices(),
    "/alerts": _mock_alerts(),
    "/incidents": _mock_incidents(),
    "/agents/logs": _mock_agent_logs(),
}


def get_mock(path: str, params: dict = None):
    for key, val in MOCK_DATA.items():
        if path.startswith(key):
            if path == "/sensors/readings" or path.startswith("/sensors"):
                minutes = int((params or {}).get("minutes", 60))
                limit = int((params or {}).get("limit", 200))
                did = (params or {}).get("device_id")
                return _mock_readings(minutes=minutes, limit=limit, device_id=did)
            return val
    return None


# ============================================================
# API helpers — real first, demo fallback
# ============================================================
def api_get(path: str, params: dict = None):
    if not st.session_state.demo_mode:
        try:
            headers = {}
            if st.session_state.token:
                headers["Authorization"] = f"Bearer {st.session_state.token}"
            r = requests.get(f"{API_BASE}{path}", params=params, headers=headers, timeout=5)
            if r.status_code == 200:
                return r.json()
        except requests.exceptions.RequestException:
            st.session_state.demo_mode = True
    return get_mock(path, params)


def api_post(path: str, json_body: dict = None, params: dict = None):
    if st.session_state.demo_mode:
        st.info("📡 Demo mode — action simulated (no live backend).")
        return {"status": "simulated", "message": "Running in demo mode"}
    try:
        headers = {}
        if st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        r = requests.post(
            f"{API_BASE}{path}",
            json=json_body,
            params=params,
            headers=headers,
            timeout=300,
        )
        if r.status_code in (200, 201):
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except requests.exceptions.RequestException:
        st.session_state.demo_mode = True
        st.info("📡 Demo mode — action simulated.")
        return {"status": "simulated"}


# ============================================================
# Sidebar - nav + login status
# ============================================================
with st.sidebar:
    st.title("🛰️ AIOps IoT Monitor")
    st.caption("Secure IoT & Electronics Monitoring")

    if st.session_state.token:
        st.success(f"Logged in: {st.session_state.username} ({st.session_state.role})")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.role = None
            st.session_state.username = None
            st.rerun()
    else:
        st.info("Not logged in (read-only mode)")

    st.divider()
    page = st.radio(
        "Navigation",
        [
            "📊 Overview",
            "📡 Devices",
            "🌡️ Sensors",
            "⚠️ Alerts",
            "🚨 Incidents",
            "🤖 Agent Logs",
            "📈 Analytics",
            "📷 Device QR Codes",
            "🔐 Admin / Auth",
        ],
    )

    st.divider()
    health = api_get("/health")
    if st.session_state.demo_mode:
        st.warning("📡 Demo Mode — live data when backend is connected")
    elif health:
        st.success("✅ API: online")
    st.caption(f"API: `{API_BASE}`")


# ============================================================
# Page 1: Overview
# ============================================================
def page_overview():
    st.title("📊 Operational Overview")
    st.caption("Real-time AIOps health snapshot — auto-refresh on load")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data — connect a live backend to see real readings")

    summary = api_get("/stats/summary")
    if not summary:
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Devices Total", summary["devices_total"])
    c2.metric("Devices Active", summary["devices_active"])
    c3.metric("Readings (24h)", f"{summary['readings_24h']:,}")
    c4.metric("Agent Runs (24h)", summary["agent_runs_24h"])

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Open Alerts", summary["alerts_open"], delta=summary["alerts_critical"], delta_color="inverse")
    c2.metric("Critical Alerts", summary["alerts_critical"])
    c3.metric("Open Incidents", summary["incidents_open"])

    st.divider()
    st.subheader("Recent Alerts")
    alerts = api_get("/alerts", {"limit": 10})
    if alerts:
        df = pd.DataFrame(alerts)
        if not df.empty:
            cols = [c for c in ["timestamp", "device_id", "severity", "alert_type", "agent_source", "resolved"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No alerts yet.")
    else:
        st.info("No alerts yet.")


# ============================================================
# Page 2: Devices
# ============================================================
def page_devices():
    st.title("📡 Device Fleet")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data")
    devices = api_get("/devices")
    if not devices:
        st.warning("No devices found.")
        return
    df = pd.DataFrame(devices)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    c2.metric("Active", int(df["is_active"].sum()) if "is_active" in df else 0)
    if "auth_status" in df:
        c3.metric("Authenticated", int((df["auth_status"] == "authenticated").sum()))
        c4.metric("Suspicious", int(df["auth_status"].isin(["suspicious", "unauthorized"]).sum()))

    st.divider()
    st.subheader("Devices")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if "battery_level" in df:
        st.subheader("Battery Levels")
        fig = px.bar(
            df.sort_values("battery_level"),
            x="device_id", y="battery_level",
            color="battery_level",
            color_continuous_scale=["red", "orange", "yellow", "green"],
            range_color=[0, 100],
        )
        fig.add_hline(y=15, line_dash="dash", line_color="red", annotation_text="Critical")
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Page 3: Sensors
# ============================================================
def page_sensors():
    st.title("🌡️ Sensor Telemetry")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data")

    devices = api_get("/devices")
    if not devices:
        st.warning("No devices found.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        device_options = ["All"] + [d["device_id"] for d in devices]
        selected = st.selectbox("Device", device_options)
    with c2:
        minutes = st.slider("Time window (minutes)", 15, 1440, 60)

    params = {"minutes": minutes, "limit": 500}
    if selected != "All":
        params["device_id"] = selected
    readings = api_get("/sensors/readings", params)

    if not readings:
        st.info("No readings in this time window.")
        return

    df = pd.DataFrame(readings)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    st.caption(f"{len(df)} readings in the last {minutes} minutes")

    metric_choice = st.selectbox(
        "Metric",
        [c for c in ["temperature", "humidity", "vibration", "battery", "signal_strength"] if c in df.columns],
    )

    if selected == "All":
        fig = px.line(df, x="timestamp", y=metric_choice, color="device_id",
                      title=f"{metric_choice.title()} over time")
    else:
        fig = px.line(df, x="timestamp", y=metric_choice,
                      title=f"{metric_choice.title()} - {selected}")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Raw readings")
    st.dataframe(df.tail(50), use_container_width=True, hide_index=True)


# ============================================================
# Page 4: Alerts
# ============================================================
def page_alerts():
    st.title("⚠️ Alerts")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data")
    c1, c2, c3 = st.columns(3)
    severity = c1.selectbox("Severity filter", ["All", "critical", "high", "medium", "low"])
    resolved = c2.selectbox("Status", ["Open only", "All", "Resolved only"])
    limit = c3.number_input("Limit", 10, 500, 100)

    params = {"limit": limit}
    if severity != "All":
        params["severity"] = severity
    if resolved == "Open only":
        params["resolved"] = "false"
    elif resolved == "Resolved only":
        params["resolved"] = "true"

    alerts = api_get("/alerts", params)
    if not alerts:
        st.info("No alerts match the filter.")
        return

    df = pd.DataFrame(alerts)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    if "severity" in df:
        c2.metric("Critical", int((df["severity"] == "critical").sum()))
        c3.metric("High", int((df["severity"] == "high").sum()))
        c4.metric("Open", int((~df["resolved"]).sum()) if "resolved" in df else 0)

    st.divider()

    if "severity" in df and len(df) > 0:
        fig = px.pie(df, names="severity", title="Alert Severity Distribution",
                     color="severity",
                     color_discrete_map={
                         "critical": "#d62728", "high": "#ff7f0e",
                         "medium": "#ffbb33", "low": "#2ca02c",
                     })
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# Page QR: Device QR Codes
# ============================================================
def page_qr():
    st.title("📷 Device QR Codes")
    st.caption("Each QR code links directly to this device's live telemetry page.")
    if st.session_state.demo_mode:
        st.info("📡 QR codes require a live backend connection.")
        st.write("When the backend is running, QR codes for all 20 devices will appear here.")
        return

    devices = api_get("/devices")
    if not devices:
        st.warning("No devices found.")
        return

    dashboard_url = st.text_input(
        "Dashboard base URL",
        value=API_BASE.replace("8000", "8501"),
    )

    cols_per_row = 4
    for i in range(0, len(devices), cols_per_row):
        row_devices = devices[i:i+cols_per_row]
        cols = st.columns(len(row_devices))
        for col, device in zip(cols, row_devices):
            with col:
                qr_url = f"{API_BASE}/devices/{device['device_id']}/qr?dashboard_url={dashboard_url}"
                try:
                    resp = requests.get(qr_url, timeout=5)
                    if resp.status_code == 200:
                        import base64
                        b64 = base64.b64encode(resp.content).decode()
                        st.markdown(
                            f'<img src="data:image/png;base64,{b64}" width="160">',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"**{device['device_id']}**")
                except Exception:
                    st.caption(f"{device['device_id']} — QR unavailable")


# ============================================================
# Page 5: Incidents
# ============================================================
def page_incidents():
    st.title("🚨 Classified Incidents")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data")
    c1, c2 = st.columns(2)
    classification = c1.selectbox("Classification", ["All", "security", "operational", "environmental"])
    status = c2.selectbox("Status", ["All", "open", "investigating", "resolved", "false_positive"])

    params = {"limit": 200}
    if classification != "All":
        params["classification"] = classification
    if status != "All":
        params["status_filter"] = status

    incidents = api_get("/incidents", params)
    if not incidents:
        st.info("No incidents match the filter.")
        return

    df = pd.DataFrame(incidents)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", len(df))
    if "classification" in df:
        c2.metric("Security", int((df["classification"] == "security").sum()))
        c3.metric("Open", int((df["status"] == "open").sum()) if "status" in df else 0)

    if "classification" in df and len(df) > 0:
        fig = px.bar(df.groupby(["classification", "severity"]).size().reset_index(name="count"),
                     x="classification", y="count", color="severity",
                     title="Incidents by classification & severity")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Incident details (with agent recommendations)")
    for _, row in df.iterrows():
        sev = row.get("severity", "low")
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
        with st.expander(
            f"{emoji} {row['threat_type']} — {row['device_id']} — {row.get('classification', '')} — {sev}"
        ):
            st.write(f"**Detected:** {row.get('detected_at', '')}")
            st.write(f"**Status:** {row.get('status', '')}")
            st.write(f"**Recommendation:** {row.get('recommendation', '_no recommendation yet_')}")


# ============================================================
# Page 6: Agent Logs
# ============================================================
def page_agent_logs():
    st.title("🤖 Agent Audit Trail")
    st.caption("Identity-aware agent decision log — every action signed and validated")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data")

    agent_filter = st.selectbox(
        "Agent",
        ["All", "telemetry_ingestion", "device_health", "anomaly_detector",
         "security", "incident_classifier", "response_recommender", "validator",
         "pipeline_orchestrator"]
    )
    params = {"limit": 200}
    if agent_filter != "All":
        params["agent_name"] = agent_filter

    logs = api_get("/agents/logs", params)
    if not logs:
        st.info("No agent logs yet.")
        return

    df = pd.DataFrame(logs)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total entries", len(df))
    if "validation_status" in df:
        c2.metric("Validated", int((df["validation_status"] == "validated").sum()))
        c3.metric("Pending/Rejected", int((df["validation_status"] != "validated").sum()))

    if "agent_name" in df and len(df) > 0:
        fig = px.histogram(df, x="agent_name", color="validation_status",
                           title="Agent activity")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Detailed log entries")
    for _, row in df.head(30).iterrows():
        with st.expander(f"[{row.get('timestamp')}] {row.get('agent_name')} — {row.get('task')}"):
            st.write(f"**Role:** {row.get('agent_role', '')}")
            st.write(f"**Validation:** {row.get('validation_status', '')}")
            st.write(f"**Execution:** {row.get('execution_time_ms', 0)} ms")
            st.write(f"**Input:** {row.get('input_summary', '')}")
            st.write("**Output:**")
            st.code(row.get("output", ""), language="text")


# ============================================================
# Page 7: Analytics
# ============================================================
def page_analytics():
    st.title("📈 Analytics & Trends")
    if st.session_state.demo_mode:
        st.info("📡 Showing demo data")

    minutes = st.slider("Time window (hours)", 1, 168, 24) * 60
    readings = api_get("/sensors/readings", {"minutes": minutes, "limit": 5000})
    alerts = api_get("/alerts", {"limit": 500})

    if readings:
        df = pd.DataFrame(readings)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        st.subheader("Sensor distributions")
        c1, c2 = st.columns(2)
        with c1:
            if "temperature" in df:
                fig = px.histogram(df, x="temperature", nbins=40, title="Temperature distribution")
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            if "vibration" in df:
                fig = px.histogram(df, x="vibration", nbins=40, title="Vibration distribution")
                st.plotly_chart(fig, use_container_width=True)

        st.subheader("Per-device activity")
        per_device = df.groupby("device_id").size().reset_index(name="readings")
        fig = px.bar(per_device.sort_values("readings", ascending=False).head(20),
                     x="device_id", y="readings", title="Top reporting devices")
        st.plotly_chart(fig, use_container_width=True)

    if alerts:
        df_a = pd.DataFrame(alerts)
        if not df_a.empty and "alert_type" in df_a:
            st.subheader("Alert types")
            fig = px.bar(df_a["alert_type"].value_counts().reset_index(),
                         x="alert_type", y="count", title="Most common alert types")
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Page 8: Admin / Auth
# ============================================================
def page_admin():
    st.title("🔐 Admin & Authentication")

    if st.session_state.demo_mode:
        st.warning("📡 Running in Demo Mode — controls are simulated. Connect a live backend to enable full functionality.")

    if not st.session_state.token and not st.session_state.demo_mode:
        st.subheader("Login")
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username", value="admin")
            password = st.text_input("Password", type="password", value="admin123")
            if st.button("Login"):
                resp = api_post("/auth/login", {"username": username, "password": password})
                if resp:
                    st.session_state.token = resp.get("access_token", "demo")
                    st.session_state.role = resp.get("role", "admin")
                    st.session_state.username = username
                    st.success(f"Logged in as {username}")
                    st.rerun()
        with c2:
            st.info(
                "Default users (demo):\n\n"
                "- `admin` / `admin123` (full access)\n"
                "- `operator` / `operator123` (read + resolve)"
            )
        return

    if st.session_state.demo_mode:
        st.success("Demo admin session active")
    else:
        st.success(f"Logged in as **{st.session_state.username}** (role: {st.session_state.role})")
    st.divider()

    st.subheader("System Controls")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.write("**1. Seed Simulator**")
        device_count = st.number_input("Devices", 5, 50, 12)
        readings_per_device = st.number_input("Readings/device", 50, 1000, 100)
        if st.button("Seed Now"):
            with st.spinner("Generating devices and readings..."):
                r = api_post("/sim/seed", params={
                    "device_count": device_count,
                    "readings_per_device": readings_per_device,
                    "anomaly_rate": 0.08,
                })
                if r:
                    st.success(f"Done: {r.get('message', r)}")

    with c2:
        st.write("**2. Train ML Model**")
        st.caption("Trains IsolationForest on stored readings")
        if st.button("Train Model"):
            with st.spinner("Training..."):
                r = api_post("/ml/train")
                if r:
                    st.success(f"Done: {r.get('message', r)}")

    with c3:
        st.write("**3. Run Agent Pipeline**")
        st.caption("Triggers all 7 CrewAI agents (requires Ollama)")
        verbose = st.checkbox("Verbose output", value=False)
        if st.button("Run Crew", type="primary"):
            with st.spinner("Running 7-agent pipeline..."):
                r = api_post("/agents/run", {
                    "user_request": "Run standard AIOps monitoring sweep",
                    "verbose": verbose,
                })
                if r:
                    st.success(f"Pipeline: {r.get('message', r.get('status', 'done'))}")


# ============================================================
# Main router
# ============================================================
PAGES = {
    "📊 Overview": page_overview,
    "📡 Devices": page_devices,
    "🌡️ Sensors": page_sensors,
    "⚠️ Alerts": page_alerts,
    "🚨 Incidents": page_incidents,
    "🤖 Agent Logs": page_agent_logs,
    "📈 Analytics": page_analytics,
    "📷 Device QR Codes": page_qr,
    "🔐 Admin / Auth": page_admin,
}

PAGES[page]()
