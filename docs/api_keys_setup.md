# API Keys & Secrets Management Guide

## Philosophy: Free-First

This project is designed to run **100% free** using Ollama locally.
Only `OPENAI_API_KEY` is optional — leave it blank to use Ollama.

---

## Local Development

```bash
cp .env.example .env
# Edit .env — only change what you need
```

Minimum `.env` for local dev (no OpenAI needed):
```env
DATABASE_URL=sqlite:///./aiops_iot.db
JWT_SECRET=any-random-string-32-chars-min
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
ADMIN_PASSWORD=admin123
```

The `.env` file is in `.gitignore` — it is **never committed**.

---

## GitHub Secrets (for CI/CD)

Go to: **Repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value | Used by |
|---|---|---|
| `DOCKERHUB_USERNAME` | Your Docker Hub username | CI/CD image push |
| `DOCKERHUB_TOKEN` | Docker Hub access token (not password) | CI/CD image push |
| `JWT_SECRET` | Random 32-char string | Test runs |

To create a Docker Hub access token:
1. hub.docker.com → Account Settings → Security → New Access Token
2. Name it `github-actions`, copy it immediately
3. Paste into GitHub Secrets as `DOCKERHUB_TOKEN`

---

## Streamlit Cloud (dashboard)

Go to: **App dashboard → Settings → Secrets**

Paste this (replace with your actual backend URL):
```toml
STREAMLIT_API_BASE = "https://YOUR-BACKEND.up.railway.app"
```

Streamlit encrypts secrets at rest. Never commit `.streamlit/secrets.toml`.

---

## Google Colab

In the Colab notebook, secrets are set inline in Cell 3:
```python
os.environ['JWT_SECRET'] = 'colab-demo-secret'
```

For real deployments using Colab + OpenAI:
```python
from google.colab import userdata
os.environ['OPENAI_API_KEY'] = userdata.get('OPENAI_API_KEY')
```
Set via: **Colab → Secrets (left panel) → Add new secret**

---

## Never Commit

The following are always in `.gitignore`:
- `.env`
- `.streamlit/secrets.toml`
- `*.db` (SQLite files)
- `backend/ml/saved_models/` (trained model files)
