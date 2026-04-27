FROM python:3.11-slim

WORKDIR /app

# System deps for bcrypt + reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY .env.example .env.example

# Create DB dir
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
