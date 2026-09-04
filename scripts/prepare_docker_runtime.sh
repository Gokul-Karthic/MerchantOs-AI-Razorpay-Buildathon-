#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$ROOT/runtime"
mkdir -p "$RUNTIME/artifacts"

if [[ -f "$ROOT/merchantos.db" && ! -f "$RUNTIME/merchantos.db" ]]; then
  cp "$ROOT/merchantos.db" "$RUNTIME/merchantos.db"
  echo "Copied merchantos.db into runtime/."
elif [[ ! -f "$RUNTIME/merchantos.db" ]]; then
  echo "No merchantos.db found. Docker will create a fresh empty Test Mode database."
fi

for file in risknet_hybrid_v2.joblib risknet_hybrid_v2_manifest.json; do
  if [[ -f "$ROOT/artifacts/$file" && ! -f "$RUNTIME/artifacts/$file" ]]; then
    cp "$ROOT/artifacts/$file" "$RUNTIME/artifacts/$file"
    echo "Copied artifacts/$file into runtime/artifacts/."
  fi
done

if [[ ! -f "$RUNTIME/artifacts/risknet_hybrid_v2.joblib" ]]; then
  echo "NOTE: locked RiskNet artifact is not present in runtime/artifacts/."
  echo "MerchantOS will use its safe operational policy fallback and will NOT silently retrain while MERCHANTOS_ALLOW_MODEL_REFIT=false."
fi

if [[ ! -f "$ROOT/.env" ]]; then
  echo "ERROR: .env is missing. Copy .env.example to .env and configure Razorpay Test Mode credentials." >&2
  exit 1
fi

echo "Docker runtime prepared at $RUNTIME"
