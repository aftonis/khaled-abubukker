"""
Output Generators
==================
Two simple, visual outputs:
  1. QR Code  - per device, links to its dashboard page
  2. PDF Report - professional incident report after each crew run
"""

import io
import os
from datetime import datetime
from typing import List, Dict, Optional

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ── QR Code ────────────────────────────────────────────────────────────────

def generate_device_qr(device_id: str, dashboard_base_url: str) -> bytes:
    """
    Generate a QR code PNG (bytes) that links to the device's
    dashboard page.  Scan it → opens live telemetry in a browser.
    """
    url = f"{dashboard_base_url}?device={device_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_base64(device_id: str, dashboard_base_url: str) -> str:
    """Return QR as base64 string for embedding in HTML/Streamlit."""
    import base64
    png_bytes = generate_device_qr(device_id, dashboard_base_url)
    return base64.b64encode(png_bytes).decode("utf-8")


# ── PDF Incident Report ─────────────────────────────────────────────────────

SEVERITY_COLORS = {
    "critical": colors.HexColor("#d62728"),
    "high":     colors.HexColor("#ff7f0e"),
    "medium":   colors.HexColor("#ffbb33"),
    "low":      colors.HexColor("#2ca02c"),
}


def generate_incident_report(
    incidents: List[Dict],
    alerts: List[Dict],
    agent_logs: List[Dict],
    stats: Dict,
    run_timestamp: Optional[str] = None,
) -> bytes:
    """
    Generate a professional A4 PDF incident report.
    Returns raw PDF bytes — caller writes to file or streams to download.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=20, textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4, alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "Heading", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#1a1a2e"),
        spaceBefore=10, spaceAfter=4,
    )
    body = styles["Normal"]
    body.fontSize = 9

    ts = run_timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    story = []

    # ── Cover ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("🛰️ AIOps IoT Monitoring", title_style))
    story.append(Paragraph("Automated Incident Report", styles["Heading3"]))
    story.append(Paragraph(f"Generated: {ts}", body))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a1a2e")))
    story.append(Spacer(1, 6*mm))

    # ── Executive summary ──────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", heading_style))
    open_inc  = sum(1 for i in incidents if i.get("status") == "open")
    critical  = sum(1 for i in incidents if i.get("severity") == "critical")
    security  = sum(1 for i in incidents if i.get("classification") == "security")
    summary_data = [
        ["Metric", "Value"],
        ["Total Incidents", str(len(incidents))],
        ["Open Incidents",  str(open_inc)],
        ["Critical Severity", str(critical)],
        ["Security Class.", str(security)],
        ["Total Alerts",   str(len(alerts))],
        ["Devices Monitored", str(stats.get("devices_total", "—"))],
        ["Readings (24h)",    str(stats.get("readings_24h", "—"))],
        ["Agent Runs (24h)",  str(stats.get("agent_runs_24h", "—"))],
    ]
    t = Table(summary_data, colWidths=[80*mm, 60*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # ── Incidents table ────────────────────────────────────────────────────
    story.append(Paragraph("Classified Incidents", heading_style))
    if incidents:
        inc_data = [["#", "Device", "Threat Type", "Class.", "Severity", "Status"]]
        for i, inc in enumerate(incidents[:50], 1):
            inc_data.append([
                str(i),
                inc.get("device_id", ""),
                inc.get("threat_type", ""),
                inc.get("classification", ""),
                inc.get("severity", ""),
                inc.get("status", ""),
            ])
        t2 = Table(inc_data, colWidths=[10*mm, 35*mm, 40*mm, 28*mm, 22*mm, 22*mm])
        ts2 = TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f9f9f9"), colors.white]),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING",  (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ])
        # Colour severity cells
        for row_idx, inc in enumerate(incidents[:50], 1):
            sev = inc.get("severity", "low")
            bg = SEVERITY_COLORS.get(sev, colors.white)
            ts2.add("BACKGROUND", (4, row_idx), (4, row_idx), bg)
            ts2.add("TEXTCOLOR",  (4, row_idx), (4, row_idx), colors.white)
        t2.setStyle(ts2)
        story.append(t2)
    else:
        story.append(Paragraph("No incidents recorded in this run.", body))
    story.append(Spacer(1, 6*mm))

    # ── Recommendations ────────────────────────────────────────────────────
    recs = [i for i in incidents if i.get("recommendation")]
    if recs:
        story.append(Paragraph("Agent Remediation Recommendations", heading_style))
        for inc in recs[:20]:
            sev   = inc.get("severity", "low")
            emoji = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}.get(sev,"⚪")
            story.append(Paragraph(
                f"<b>{emoji} {inc.get('device_id')} — {inc.get('threat_type')}</b>",
                body,
            ))
            story.append(Paragraph(
                f"&nbsp;&nbsp;&nbsp;{inc.get('recommendation', '')}",
                body,
            ))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 4*mm))

    # ── Agent audit trail ──────────────────────────────────────────────────
    story.append(Paragraph("Agent Audit Trail (last 20 entries)", heading_style))
    if agent_logs:
        log_data = [["Agent", "Task", "Validation", "Time (ms)"]]
        for log in agent_logs[:20]:
            log_data.append([
                log.get("agent_name", ""),
                log.get("task", ""),
                log.get("validation_status", ""),
                str(log.get("execution_time_ms", 0)),
            ])
        t3 = Table(log_data, colWidths=[45*mm, 55*mm, 40*mm, 25*mm])
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f9f9f9"),colors.white]),
            ("LEFTPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING", (0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ]))
        story.append(t3)
    else:
        story.append(Paragraph("No agent logs available.", body))

    # ── Footer ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Paragraph(
        "Generated by AIOps IoT Monitoring Platform · 7-Agent CrewAI Pipeline · "
        "IsolationForest Anomaly Detection · Identity-Aware Agents",
        ParagraphStyle("footer", parent=body, fontSize=7,
                       textColor=colors.HexColor("#888888"), alignment=TA_CENTER),
    ))

    doc.build(story)
    return buf.getvalue()


if __name__ == "__main__":
    # Smoke test
    print("[QR] Generating device QR...")
    png = generate_device_qr("IOT-1000", "http://localhost:8501")
    print(f"[QR] PNG bytes: {len(png)}")

    print("[PDF] Generating incident report...")
    dummy_incidents = [
        {"device_id":"IOT-1000","threat_type":"temp_spike","classification":"environmental",
         "severity":"high","status":"open","recommendation":"Check HVAC in Zone A"},
        {"device_id":"IOT-1003","threat_type":"tampering","classification":"security",
         "severity":"critical","status":"open","recommendation":"Quarantine device immediately"},
    ]
    dummy_alerts = [{"device_id":"IOT-1000","severity":"high","alert_type":"temp_spike"}] * 5
    dummy_logs = [{"agent_name":"anomaly_detector","task":"scan","validation_status":"validated","execution_time_ms":210}]
    dummy_stats = {"devices_total":12,"readings_24h":1200,"agent_runs_24h":3}
    pdf_bytes = generate_incident_report(dummy_incidents, dummy_alerts, dummy_logs, dummy_stats)
    print(f"[PDF] PDF bytes: {len(pdf_bytes)}")
    with open("/tmp/test_report.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("[PDF] Saved to /tmp/test_report.pdf")
