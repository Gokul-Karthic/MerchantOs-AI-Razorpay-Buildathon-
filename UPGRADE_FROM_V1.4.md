# Upgrade from v1.4 to v1.4.1

v1.4.1 is a code/governance hardening release. It does not retrain RiskNet.

From the extracted v1.4.1 folder:

```bash
bash scripts/migrate_from_previous.sh ../MerchantOS_AI_v1.4_LivePaymentTrace_Docker
bash scripts/prepare_docker_runtime.sh
docker compose up --build -d
docker compose ps
python3 scripts/system_check.py
```

The migration script prefers the previous Docker `runtime/merchantos.db` when it contains richer state. Your `.env` remains local and is never included in the clean release archive.
