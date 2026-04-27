# V-Model Lifecycle Mapping

## AIOps IoT Monitoring — V-Model SDLC

This document maps every project deliverable to the V-Model stage
that produced it, demonstrating structured lifecycle adherence.

---

## Left Arm (Definition)

### Requirements Analysis
- **File:** `docs/requirements_traceability.md`
- **Artefacts:** 18 functional + 8 non-functional requirements
- **Validation level:** Acceptance Testing

### System Design
- **Files:** `docs/architecture.md`, `README.md` (Architecture section)
- **Artefacts:** Component diagram, DB schema diagram, agent pipeline diagram
- **Validation level:** System Testing

### Architecture Design
- **Files:** `backend/db/models.py`, `backend/api/main.py`
- **Artefacts:** 5-table SQLite schema, 22-endpoint FastAPI spec, CrewAI 5-Pillar pattern
- **Validation level:** Integration Testing

### Module Design
- **Files:** `backend/crew/agents.py`, `backend/crew/tasks.py`, `backend/crew/tools.py`
- **Artefacts:** 7 agents × roles/permissions, 6 custom tools, task specifications
- **Validation level:** Unit Testing

---

## Bottom (Implementation)

### Coding
- `backend/` — Python, FastAPI, CrewAI, SQLAlchemy, IsolationForest
- `dashboard/app.py` — Streamlit (9 pages)
- `backend/auth/identity.py` — Identity-aware agent JWT layer
- `backend/outputs.py` — QR codes (qrcode) + PDF reports (ReportLab)

---

## Right Arm (Validation)

### Unit Testing
- **Files:** `tests/unit/test_db_schema.py`, `tests/unit/test_simulator_and_ml.py`, `tests/unit/test_auth.py`
- **Coverage:** DB schema (5 tests), simulator (6 tests), ML detector (5 tests), auth (8 tests)
- **Result:** 24/24 passing

### Integration Testing
- **File:** `tests/integration/test_api.py`
- **Coverage:** 18 API endpoint integration tests
- **Method:** FastAPI TestClient with isolated SQLite DB per test

### Agent Behaviour Validation
- **File:** `tests/agent_validation/test_agent_tools.py`
- **Coverage:** All 6 custom CrewAI tools tested without LLM invocation
- **Key validations:** Permission enforcement, audit log integrity, DB write correctness

### System Testing
- **Method:** `docker-compose up --build` → seed → train → run crew
- **KPIs validated:**
  - Alert generation rate matches injected anomaly rate (~8%)
  - JWT tokens issued for all 7 agents, scoped permissions enforced
  - PDF report generates within 2 seconds
  - QR codes resolve to correct device URLs

### Acceptance Testing
- **Method:** Streamlit dashboard end-to-end walkthrough
- **Business KPIs:**
  - Operations team can see all open incidents in < 3 clicks
  - Each incident has an AI-generated recommendation
  - Every agent decision is auditable (identity hash in log)
  - Downloadable PDF report generated on demand
  - Device QR codes scannable and link to live telemetry

---

## Rapid Application Development Integration

RAD was applied within each V-Model phase:
- **Iteration 1:** Schema + simulator (validate data shape before code)
- **Iteration 2:** ML detector in isolation (validate anomaly detection accuracy)
- **Iteration 3:** API endpoints with TestClient (validate before dashboard)
- **Iteration 4:** Dashboard pages iteratively, one at a time
- **Iteration 5:** CI/CD pipeline added as final layer

This Simulate → Validate → Build discipline ensured no integration
surprises when all components were connected.
