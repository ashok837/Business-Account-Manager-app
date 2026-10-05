FROM python:3.12-slim

WORKDIR /app

# System deps for mysqlclient/cryptography wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run migrations, then start the API. In production behind a load balancer,
# put uvicorn behind a process manager / increase --workers as needed.
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000
