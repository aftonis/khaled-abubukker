"""
CrewAI Tasks
=============
One task per agent in the AIOps pipeline. Tasks pass context to each other
via crew sequencing.
"""

from crewai import Task
from typing import List


def build_ingestion_task(agent) -> Task:
    return Task(
        description=(
            "Fetch the most recent 60 minutes of sensor readings from the database. "
            "Validate that each reading has all required fields (temperature, humidity, "
            "vibration, battery, signal_strength) and that values are within physically "
            "plausible ranges. Report the total count, any malformed readings, and a "
            "brief summary of the data quality."
        ),
        expected_output=(
            "A short report (3-5 sentences) covering: total readings retrieved, "
            "number of devices reporting, any data-quality issues, and overall pipeline health."
        ),
        agent=agent,
    )


def build_health_task(agent) -> Task:
    return Task(
        description=(
            "Inspect every registered device using check_device_health. "
            "Identify devices with: battery below 15%, auth_status not 'authenticated', "
            "or last_seen more than 30 minutes ago. For each problematic device, write an "
            "alert using write_alert with the appropriate severity and alert_type "
            "(battery_critical, auth_compromised, device_offline). Set agent_source='device_health'."
        ),
        expected_output=(
            "A list of devices flagged for attention, each with the issue and the alert ID created."
        ),
        agent=agent,
    )


def build_anomaly_task(agent) -> Task:
    return Task(
        description=(
            "Run run_anomaly_detection over the last 60 minutes of telemetry. "
            "For EACH anomaly returned, write an alert using write_alert with: "
            "the device_id, severity from the result, alert_type from the result, "
            "a description naming the offending values, and agent_source='anomaly_detector'. "
            "Limit yourself to writing alerts for at most the top 10 most severe anomalies "
            "to avoid alert fatigue."
        ),
        expected_output=(
            "A summary listing how many readings were scanned, how many anomalies detected, "
            "and the IDs of alerts written."
        ),
        agent=agent,
    )


def build_security_task(agent) -> Task:
    return Task(
        description=(
            "Cross-reference device health and recent telemetry to look for security-relevant "
            "patterns: devices with auth_status of 'unauthorized' or 'suspicious', sudden "
            "vibration spikes that could indicate physical tampering, or correlated multi-sensor "
            "anomalies that suggest firmware compromise. For any genuine security concern, "
            "write an incident using write_incident with classification='security'."
        ),
        expected_output=(
            "A short security report listing any security incidents created, with device IDs and threat types."
        ),
        agent=agent,
    )


def build_classification_task(agent) -> Task:
    return Task(
        description=(
            "Fetch open alerts using fetch_open_alerts. For each alert that doesn't yet "
            "have a corresponding incident, classify it by: classification (security / "
            "operational / environmental) and severity. Create an incident using write_incident. "
            "For environmental alerts (temp/humidity), classification is 'environmental'. "
            "For battery/firmware/connectivity, classification is 'operational'. "
            "For tampering/auth, classification is 'security'."
        ),
        expected_output=(
            "A list of incidents created, grouped by classification, with counts."
        ),
        agent=agent,
    )


def build_response_task(agent) -> Task:
    return Task(
        description=(
            "Review the open incidents and provide concrete remediation recommendations. "
            "Map each threat_type to a specific runbook step:\n"
            "- temp_spike / temp_drop → 'Check HVAC system in {location} and verify cold-chain integrity'\n"
            "- humidity_flood → 'Inspect for water ingress and ventilation issues'\n"
            "- vibration_spike → 'Send technician to inspect device for tampering or mechanical fault'\n"
            "- battery_critical → 'Schedule battery replacement within 24 hours'\n"
            "- signal_loss → 'Verify network connectivity and gateway health'\n"
            "- tampering / unauthorized_firmware → 'Quarantine device immediately and escalate to security team'\n"
            "Output a prioritised action list."
        ),
        expected_output=(
            "A prioritised list of remediation actions, ordered critical → low, "
            "with specific device_ids and recommended steps."
        ),
        agent=agent,
    )


def build_validation_task(agent) -> Task:
    return Task(
        description=(
            "Review the work of the previous agents in this run. Apply strict validation:\n"
            "1. Are the alert severities consistent with the sensor values mentioned?\n"
            "2. Are the recommendations actionable (specific device_ids, concrete steps)?\n"
            "3. Are there any hallucinated device IDs or values not grounded in the data?\n"
            "4. Are environmental alerts not misclassified as security?\n"
            "Produce a final validation report. If everything checks out, mark as 'validated'. "
            "If issues are found, list them and mark as 'needs_human_review'."
        ),
        expected_output=(
            "A validation report with status (validated / needs_human_review), "
            "a count of items reviewed, and any issues flagged."
        ),
        agent=agent,
    )


# Registry mapping
TASK_BUILDERS = {
    "telemetry_ingestion": build_ingestion_task,
    "device_health": build_health_task,
    "anomaly_detector": build_anomaly_task,
    "security": build_security_task,
    "incident_classifier": build_classification_task,
    "response_recommender": build_response_task,
    "validator": build_validation_task,
}
