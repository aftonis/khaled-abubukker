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
import requests
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


# ============================================================
# API helpers
# ============================================================
def api_get(path: str, params: dict = None):
    try:
        headers = {}
        if st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        r = requests.get(f"{API_BASE}{path}", params=params, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Cannot reach API at {API_BASE}: {e}")
        return None


def api_post(path: str, json_body: dict = None, params: dict = None):
    try:
        headers = {}
        if st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        r = requests.post(
            f"{API_BASE}{path}",
            json=json_body,
            params=params,
            headers=headers,
            timeout=300,  # crew run can be slow
        )
        if r.status_code in (200, 201):
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Cannot reach API at {API_BASE}: {e}")
        return None


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
    st.caption(f"API: `{API_BASE}`")
    health = api_get("/health")
    if health:
        st.success("API: online")
    else:
        st.error("API: offline")


# ============================================================
# Page 1: Overview
# ============================================================
def page_overview():
    st.title("📊 Operational Overview")
    st.caption("Real-time AIOps health snapshot — auto-refresh on load")

    summary = api_get("/stats/summary")
    if not summary:
        st.warning("Cannot load summary stats - is the API running?")
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
            df = df[["timestamp", "device_id", "severity", "alert_type", "agent_source", "resolved"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No alerts yet. Run the agent pipeline from the Admin page.")
    else:
        st.info("No alerts yet.")


# ============================================================
# Page 2: Devices
# ============================================================
def page_devices():
    st.title("📡 Device Fleet")
    devices = api_get("/devices")
    if not devices:
        st.warning("No devices found. Seed the simulator from the Admin page.")
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

    devices = api_get("/devices")
    if not devices:
        st.warning("No devices found. Seed simulator first.")
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
        ["temperature", "humidity", "vibration", "battery", "signal_strength"],
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

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    if "severity" in df:
        c2.metric("Critical", int((df["severity"] == "critical").sum()))
        c3.metric("High", int((df["severity"] == "high").sum()))
        c4.metric("Open", int((~df["resolved"]).sum()) if "resolved" in df else 0)

    st.divider()

    # Severity distribution
    if "severity" in df and len(df) > 0:
        fig = px.pie(df, names="severity", title="Alert Severity Distribution",
                     color="severity",
                     color_discrete_map={
                         "critical": "#d62728", "high": "#ff7f0e",
                         "medium": "#ffbb33", "low": "#2ca02c",
                     })
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📥 Download Incident Report")
    st.caption("Generates a professional PDF with all incidents, recommendations and audit trail.")
    pdf_url = f"{API_BASE}/reports/incidents/pdf"
    st.markdown(f"[⬇ Download PDF Report]({pdf_url})", unsafe_allow_html=True)


# ============================================================
# Page QR: Device QR Codes
# ============================================================
def page_qr():
    st.title("📷 Device QR Codes")
    st.caption("Each QR code links directly to this device's live telemetry page. Scan with any phone.")

    devices = api_get("/devices")
    if not devices:
        st.warning("No devices found. Seed the simulator from Admin page first.")
        return

    dashboard_url = st.text_input(
        "Dashboard base URL (put your deployed Streamlit URL here)",
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
                        st.caption(f"{device['location']}")
                        batt = device.get('battery_level', 0)
                        color = "🔴" if batt < 15 else "🟡" if batt < 40 else "🟢"
                        st.caption(f"{color} Battery: {batt}%")
                except Exception:
                    st.caption(f"{device['device_id']} — QR unavailable")


# ============================================================
# Page 5: Incidents
# ============================================================
def page_incidents():
    st.title("🚨 Classified Incidents")
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
        st.info("No agent logs yet. Run the pipeline from Admin page.")
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
            st.write(f"**Output:**")
            st.code(row.get("output", ""), language="text")


# ============================================================
# Page 7: Analytics
# ============================================================
def page_analytics():
    st.title("📈 Analytics & Trends")

    minutes = st.slider("Time window (hours)", 1, 168, 24) * 60
    readings = api_get("/sensors/readings", {"minutes": minutes, "limit": 5000})
    alerts = api_get("/alerts", {"limit": 500})

    if readings:
        df = pd.DataFrame(readings)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        st.subheader("Sensor distributions")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.histogram(df, x="temperature", nbins=40, title="Temperature distribution")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
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

    if not st.session_state.token:
        st.subheader("Login")
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username", value="admin")
            password = st.text_input("Password", type="password", value="admin123")
            if st.button("Login"):
                resp = api_post("/auth/login", {"username": username, "password": password})
                if resp:
                    st.session_state.token = resp["access_token"]
                    st.session_state.role = resp["role"]
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
                    st.success(f"Seeded: {r}")

    with c2:
        st.write("**2. Train ML Model**")
        st.caption("Trains IsolationForest on stored readings")
        if st.button("Train Model"):
            with st.spinner("Training..."):
                r = api_post("/ml/train")
                if r:
                    st.success(f"Trained: {r}")

    with c3:
        st.write("**3. Run Agent Pipeline**")
        st.caption("Triggers all 7 CrewAI agents (requires Ollama)")
        verbose = st.checkbox("Verbose output", value=False)
        if st.button("Run Crew", type="primary"):
            with st.spinner("Running 7-agent pipeline... (1-3 minutes)"):
                r = api_post("/agents/run", {
                    "user_request": "Run standard AIOps monitoring sweep",
                    "verbose": verbose,
                })
                if r:
                    if r.get("status") == "success":
                        st.success(f"Pipeline complete in {r['execution_time_ms']}ms")
                        st.write("**Final output:**")
                        st.code(r.get("final_output", ""))
                    else:
                        st.error(f"Pipeline error: {r.get('error', 'unknown')}")


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
