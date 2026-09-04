# Docker Guide

MerchantOS v1.4.1 ships as two containers built from one pinned Python 3.11 image:

- `api` — FastAPI on port `8000`
- `dashboard` — Streamlit on port `8501`

The API owns the SQLite database and RiskNet artifact. The dashboard only calls the API.

## First run

1. Copy your working `.env`, database, and RiskNet artifact into v1.4.1 (or run `scripts/migrate_from_previous.sh`).
2. Prepare persistent runtime state:

```bash
bash scripts/prepare_docker_runtime.sh
```

3. Build and start:

```bash
docker compose up --build -d
```

4. Check health:

```bash
docker compose ps
curl http://localhost:8000/api/health
```

5. Open `http://localhost:8501`.

## Persistent state

`runtime/` is mounted at `/data` in the API container. The compose file sets:

```text
MERCHANTOS_DB_PATH=/data/merchantos.db
MERCHANTOS_ARTIFACT_DIR=/data/artifacts
```

This separates runtime state from the immutable container image.

## Webhooks

Your public tunnel should still target host port `8000`, for example:

```text
https://<your-public-host>/api/razorpay/webhook
```

Docker publishes API port `8000`, so zrok/cloudflared can point to `http://localhost:8000` exactly as before.

## Stop / reset

Stop containers without deleting runtime state:

```bash
docker compose down
```

Rebuild after code changes:

```bash
docker compose up --build -d
```

To intentionally start with fresh runtime data, stop Docker and remove `runtime/` manually. Do not do this for your Buildathon demo unless you have backed up the current Test Mode evidence.
