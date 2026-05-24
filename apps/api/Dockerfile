FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git wget && rm -rf /var/lib/apt/lists/*
# wget is needed by docker-compose.prod.yml's healthcheck for the /health
# probe; python:3.11-slim does not ship wget/curl by default.

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
