"""
CrewAI Agents (Pillar 5: Agents & Tasks)
=========================================
7 identity-aware agents covering the AIOps lifecycle:
  1. Telemetry Ingestion  - validates incoming sensor data
  2. Device Health        - inspects device fleet (battery, firmware, auth)
  3. Anomaly Detector     - runs IsolationForest on telemetry
  4. Security             - watches for tampering, unauthorized firmware, auth fails
  5. Incident Classifier  - severity scoring + threat typing
  6. Response Recommender - suggests remediation actions
  7. Validator/Reviewer   - self-checking guardrail (Khaled's Week 15 pattern)
"""

import os
from crewai import Agent, LLM
from dotenv import load_dotenv

from backend.crew.tools import (
    FetchSensorReadingsTool, CheckDeviceHealthTool, RunAnomalyDetectionTool,
    WriteAlertTool, WriteIncidentTool, FetchOpenAlertsTool,
)

load_dotenv()


# ============================================================
# LLM Configuration (Pillar 1: Setup & Tools)
# Ollama-first, OpenAI fallback - matches Khaled's standard pattern
# ============================================================

def get_llm() -> LLM:
    """Build LLM with Ollama primary, OpenAI fallback. Temperature discipline: 0.3."""
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # Force fallback to OpenAI if requested or Ollama unreachable + key available
    if provider == "openai" and openai_key:
        return LLM(
            model=f"openai/{os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}",
            api_key=openai_key,
            temperature=0.3,
        )

    # Default: Ollama
    return LLM(
        model=f"ollama/{os.getenv('OLLAMA_MODEL', 'llama3.2')}",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.3,
    )


# ============================================================
# 7 Agents - each with identity, role, scoped tools
# ============================================================

def build_telemetry_ingestion_agent(llm=None) -> Agent:
    return Agent(
        role="Telemetry Ingestion Specialist",
        goal=(
            "Pull recent sensor readings, validate their schema and units, and report "
            "the volume and quality of incoming telemetry."
        ),
        backstory=(
            "You are an expert in industrial IoT telemetry pipelines. You ensure that "
            "every sensor reading entering the system is well-formed and within physically "
            "plausible ranges before downstream agents consume it."
        ),
        tools=[FetchSensorReadingsTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def build_device_health_agent(llm=None) -> Agent:
    return Agent(
        role="Device Health Monitor",
        goal=(
            "Inspect every registered IoT device. Identify devices with low battery, "
            "outdated firmware, suspicious auth status, or stale telemetry."
        ),
        backstory=(
            "You are a fleet operations engineer responsible for the physical health of "
            "hundreds of warehouse sensors. You catch failing devices before they cause outages."
        ),
        tools=[CheckDeviceHealthTool(), WriteAlertTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def build_anomaly_detector_agent(llm=None) -> Agent:
    return Agent(
        role="Anomaly Detection Specialist",
        goal=(
            "Run the IsolationForest model on recent telemetry, identify anomalous readings, "
            "and write structured alerts for each detected anomaly."
        ),
        backstory=(
            "You are a data scientist specialising in unsupervised anomaly detection for "
            "industrial sensor networks. You translate ML model output into actionable alerts."
        ),
        tools=[RunAnomalyDetectionTool(), WriteAlertTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def build_security_agent(llm=None) -> Agent:
    return Agent(
        role="Security Operations Agent",
        goal=(
            "Detect security-relevant events: tampering, unauthorized firmware, auth failures. "
            "Cross-reference device health against telemetry patterns to flag suspicious activity."
        ),
        backstory=(
            "You are an OT/IoT security analyst. You understand that anomalies in sensor data "
            "can indicate physical tampering or compromise of the device firmware."
        ),
        tools=[CheckDeviceHealthTool(), FetchSensorReadingsTool(), WriteIncidentTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def build_incident_classifier_agent(llm=None) -> Agent:
    return Agent(
        role="Incident Classification Specialist",
        goal=(
            "Read open alerts, classify them by severity (low/med/high/critical) and "
            "type (security / operational / environmental), and escalate to incidents."
        ),
        backstory=(
            "You are an SRE incident commander. You triage raw alerts into structured incidents "
            "so the response team knows exactly what to act on first."
        ),
        tools=[FetchOpenAlertsTool(), WriteIncidentTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def build_response_recommender_agent(llm=None) -> Agent:
    return Agent(
        role="Response Recommendation Engine",
        goal=(
            "For each open incident, recommend a concrete remediation action: "
            "restart device, quarantine, dispatch technician, escalate to security, etc."
        ),
        backstory=(
            "You are a runbook expert who has seen thousands of IoT incidents. You map "
            "each incident type to a proven response playbook."
        ),
        tools=[FetchOpenAlertsTool(), WriteIncidentTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


def build_validator_agent(llm=None) -> Agent:
    return Agent(
        role="Decision Validator / Reviewer",
        goal=(
            "Review the outputs of other agents in the pipeline. Verify that alerts and "
            "incidents are well-formed, severities are reasonable given the data, and "
            "recommendations are actionable. Flag any hallucinated or inconsistent outputs."
        ),
        backstory=(
            "You are the final guardrail before the operations team sees anything. "
            "You apply strict validation, hallucination guarding, and self-checking principles. "
            "When in doubt, you mark items as 'needs_human_review' rather than passing them through."
        ),
        tools=[FetchOpenAlertsTool()],
        llm=llm or get_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )


# Registry
AGENT_BUILDERS = {
    "telemetry_ingestion": build_telemetry_ingestion_agent,
    "device_health": build_device_health_agent,
    "anomaly_detector": build_anomaly_detector_agent,
    "security": build_security_agent,
    "incident_classifier": build_incident_classifier_agent,
    "response_recommender": build_response_recommender_agent,
    "validator": build_validator_agent,
}
