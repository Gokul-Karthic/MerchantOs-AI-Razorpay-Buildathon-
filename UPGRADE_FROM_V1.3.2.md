# Upgrade from v1.3.2 to v1.4

v1.4 adds Live Payment Journey and Docker. The finalized RiskNet model is copied, not retrained.

```bash
cd ~/Downloads/MerchantOS_AI_v1.4_LivePaymentTrace_Docker
bash scripts/migrate_from_previous.sh ../MerchantOS_AI_v1.3.2_AlwaysVisibleSidebar
```

Verify that these now exist:

```bash
ls -l .env merchantos.db artifacts/risknet_hybrid_v2.joblib
```

Then choose Docker:

```bash
bash scripts/prepare_docker_runtime.sh
docker compose up --build -d
```

or the existing local Python workflow.

The Live Payment Journey always creates `UNLABELED` Razorpay Test Mode orders. Do not use it to create new model-training labels.
