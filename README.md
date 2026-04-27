# 🛰️ AIOps Enabled Secure IoT & Electronics Monitoring System

[![CI/CD](https://github.com/aftonis/khaled-abubukker/actions/workflows/ci.yml/badge.svg)](https://github.com/aftonis/khaled-abubukker/actions)
[![Docker Hub](https://img.shields.io/docker/v/aftonis/aiops-iot-monitoring?label=Docker%20Hub)](https://hub.docker.com/r/aftonis/aiops-iot-monitoring)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Project 2 — Assignment submission for AIOps and Agentic AI Development**

A production-grade AIOps platform that monitors simulated warehouse IoT devices using a 7-agent CrewAI pipeline, IsolationForest anomaly detection, identity-aware agents, and a full Streamlit dashboard.

---

## Quick Start (Local)

```bash
git clone https://github.com/aftonis/khaled-abubukker.git
cd khaled-abubukker
cp .env.example .env          # edit if needed
pip install -r requirements.txt
```

**Start backend:**
```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Start dashboard:**
```bash
streamlit run dashboard/app.py
```

**Or with Docker:**
```bash
docker-compose up --build
```

Then open:
- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501
- API health: http://localhost:8000/health

---

## Stack

| Layer | Technology |
|-------|-----------|
| Agent orchestration | CrewAI 0.86 |
| LLM (primary) | Ollama llama3.2 (local, free) |
| LLM (fallback) | OpenAI gpt-4o-mini |
| Backend | FastAPI + Uvicorn |
| Database | SQLite via SQLAlchemy |
| ML | scikit-learn IsolationForest |
| Dashboard | Streamlit + Plotly |
| Auth | JWT (PyJWT) + bcrypt |
| Output: QR | qrcode[pil] |
| Output: PDF | ReportLab |
| CI/CD | GitHub Actions |
| Container | Docker + Docker Compose |
| Deployment | Streamlit Cloud + Docker Hub |

---

## Architecture

```
IoT Simulator → FastAPI REST API → SQLite DB
                       ↕
              7-Agent CrewAI Crew
              ┌─────────────────────────────┐
              │ 1. Telemetry Ingestion       │
              │ 2. Device Health Monitor     │
              │ 3. Anomaly Detector (ML)     │
              │ 4. Security Agent            │
              │ 5. Incident Classifier       │
              │ 6. Response Recommender      │
              │ 7. Validator / Reviewer      │
              └─────────────────────────────┘
                       ↕
              Streamlit Dashboard (9 pages)
              + QR codes + PDF reports
```

---

## Database Schema (5 tables)

| Table | Purpose |
|-------|---------|
| `devices` | IoT device registry (firmware, battery, auth status) |
| `sensor_readings` | Telemetry (temp, humidity, vibration, battery, signal) |
| `alerts` | Anomaly flags raised by ML + agents |
| `incidents` | Classified threats with remediation recommendations |
| `agent_task_logs` | Identity-aware agent audit trail (JWT hash per entry) |

---

## Running the Agent Pipeline

1. **Seed data** — Admin page → Seed Simulator (or `POST /sim/seed`)
2. **Train model** — Admin page → Train Model (or `POST /ml/train`)
3. **Run crew** — Admin page → Run Crew (requires Ollama running with llama3.2)

Without Ollama, everything except the CrewAI run works. The Colab demo notebook demonstrates all non-LLM components.

---

## Running Tests

```bash
pytest tests/unit tests/integration -v
```

---

## Deployment

### Streamlit Cloud (dashboard — free)
1. Push repo to GitHub
2. Go to share.streamlit.io → New app → select `dashboard/app.py`
3. Add secret: `STREAMLIT_API_BASE = "https://your-backend-url"`

### Docker Hub (backend image — free)
```bash
docker build -t aftonis/aiops-iot-monitoring .
docker push aftonis/aiops-iot-monitoring
```
GitHub Actions does this automatically on push to `main`.

### API Keys needed
Only `OPENAI_API_KEY` is optional (Ollama is the free default).
Store in `.env` locally, GitHub Secrets for CI, Streamlit Secrets for dashboard.

---

## Project Structure

```
aiops-iot-monitoring/
├── backend/
│   ├── api/main.py          FastAPI (22 endpoints)
│   ├── api/schemas.py       Pydantic schemas
│   ├── db/models.py         SQLAlchemy (5 tables)
│   ├── crew/
│   │   ├── agents.py        7 identity-aware agents
│   │   ├── tasks.py         7 tasks
│   │   ├── tools.py         6 custom CrewAI tools
│   │   └── crew.py          Pipeline orchestrator
│   ├── ml/anomaly_detector.py  IsolationForest
│   ├── simulator/sensor_sim.py IoT data generator
│   ├── auth/identity.py     JWT agent + user auth
│   └── outputs.py           QR codes + PDF reports
├── dashboard/app.py         Streamlit (9 pages)
├── notebooks/demo_colab.ipynb  Self-contained Colab demo
├── tests/                   24+ pytest tests
├── .github/workflows/ci.yml GitHub Actions CI/CD
├── Jenkinsfile              Jenkins pipeline (demo)
├── Dockerfile               Backend container
├── Dockerfile.streamlit     Dashboard container
└── docker-compose.yml       Local orchestration
```
