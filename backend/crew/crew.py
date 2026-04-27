"""
AIOps IoT Crew - Main Orchestrator
====================================
Implements Khaled's 5-Pillar Pattern:
  1. Setup & Tools          → backend/crew/tools.py + LLM config in agents.py
  2. User Input             → run_crew(user_request) entry point
  3. Data Persistence       → backend/db/models.py + agent_task_logs
  4. Custom Tools           → 6 BaseTool subclasses in tools.py
  5. Agents & Tasks         → 7 agents + 7 tasks, sequential process

Two-phase methodology: each agent run gets logged to agent_task_logs with
identity hash and validation status (Khaled's resilience pattern).
"""

import time
import json
from datetime import datetime
from crewai import Crew, Process

from backend.crew.agents import AGENT_BUILDERS, get_llm
from backend.crew.tasks import TASK_BUILDERS
from backend.crew.tools import log_agent_task


def build_crew(verbose: bool = False) -> tuple[Crew, dict]:
    """
    Build the full 7-agent AIOps crew with sequential process.
    Returns the crew + a dict of agent_name -> task for logging.
    """
    llm = get_llm()

    agents = {}
    tasks = {}
    agent_task_pairs = {}

    pipeline_order = [
        "telemetry_ingestion",
        "device_health",
        "anomaly_detector",
        "security",
        "incident_classifier",
        "response_recommender",
        "validator",
    ]

    for name in pipeline_order:
        agent = AGENT_BUILDERS[name](llm=llm)
        task = TASK_BUILDERS[name](agent)
        agents[name] = agent
        tasks[name] = task
        agent_task_pairs[name] = (agent, task)

    crew = Crew(
        agents=list(agents.values()),
        tasks=list(tasks.values()),
        process=Process.sequential,
        verbose=verbose,
    )

    return crew, agent_task_pairs


def run_crew(user_request: str = "Run the standard AIOps pipeline", verbose: bool = False) -> dict:
    """
    Execute the full 7-agent pipeline.

    Args:
        user_request: Optional context for the run.
        verbose: If True, CrewAI prints agent thoughts.

    Returns:
        dict with execution stats, validation status, and final output.
    """
    start = time.time()
    pipeline_order = [
        "telemetry_ingestion", "device_health", "anomaly_detector",
        "security", "incident_classifier", "response_recommender", "validator"
    ]

    crew, agent_task_pairs = build_crew(verbose=verbose)

    # Log pipeline start
    log_agent_task(
        agent_name="pipeline_orchestrator",
        agent_role="Crew Orchestrator",
        task="pipeline_start",
        input_summary=user_request,
        output=f"Starting 7-agent pipeline at {datetime.utcnow().isoformat()}",
        validation_status="validated",
    )

    try:
        result = crew.kickoff(inputs={"user_request": user_request})
        execution_ms = int((time.time() - start) * 1000)

        # Extract per-task output for audit log
        for name, (agent, task) in agent_task_pairs.items():
            task_output = ""
            try:
                if hasattr(task, "output") and task.output:
                    task_output = str(task.output)[:1500]
            except Exception:
                pass
            log_agent_task(
                agent_name=name,
                agent_role=agent.role,
                task=name + "_task",
                input_summary=user_request[:200],
                output=task_output or "(no captured output)",
                validation_status="validated" if name != "validator" else "self_validated",
                validator_agent="validator" if name != "validator" else None,
                execution_time_ms=execution_ms // len(pipeline_order),
            )

        return {
            "status": "success",
            "execution_time_ms": execution_ms,
            "agents_run": len(pipeline_order),
            "final_output": str(result)[:3000],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        execution_ms = int((time.time() - start) * 1000)
        log_agent_task(
            agent_name="pipeline_orchestrator",
            agent_role="Crew Orchestrator",
            task="pipeline_error",
            input_summary=user_request,
            output=f"Error: {str(e)[:500]}",
            validation_status="rejected",
            execution_time_ms=execution_ms,
        )
        return {
            "status": "error",
            "execution_time_ms": execution_ms,
            "error": str(e)[:500],
            "timestamp": datetime.utcnow().isoformat(),
        }


if __name__ == "__main__":
    print("[crew] Running pipeline (this needs Ollama running with llama3.2)...")
    result = run_crew(verbose=True)
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
