# MerchantOS AI v1.4.1.1 — Project Handoff

The Buildathon-ready product is MerchantOS AI v1.4.1.

## Preserve from the current working installation

- `.env`
- `merchantos.db`
- `artifacts/risknet_hybrid_v2.joblib`
- `artifacts/risknet_hybrid_v2_manifest.json` when present

Use:

```bash
bash scripts/migrate_from_previous.sh ../MerchantOS_AI_v1.3.2_AlwaysVisibleSidebar
```

## Runtime recommendation

Prefer Docker Compose for the final demo:

```bash
bash scripts/prepare_docker_runtime.sh
docker compose up --build -d
```

The user-facing dashboard is `http://localhost:8501`; FastAPI is `http://localhost:8000`.

## Model policy

Do not retrain RiskNet for normal operation. Keep `MERCHANTOS_ALLOW_MODEL_REFIT=false`. Live Payment Journey transactions are operational Test Mode payments and remain `UNLABELED`.
