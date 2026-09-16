# ── TechElectro Inventory Analytics Engine ───────────────────────────────────
# Multi-stage Dockerfile: installs Microsoft ODBC Driver 17 for SQL Server
# on Debian slim, then installs Python dependencies and runs Streamlit.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# Install system dependencies for ODBC Driver 17 (pyodbc on Linux)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        apt-transport-https \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor \
        -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql17 \
        unixodbc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Application layer ─────────────────────────────────────────────────────────
FROM base AS app

WORKDIR /app

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .
COPY generate_charts.py .
COPY .streamlit/ .streamlit/

# Expose Streamlit default port
EXPOSE 8501

# Health check — Streamlit exposes a built-in health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the dashboard
CMD ["python", "-m", "streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]

