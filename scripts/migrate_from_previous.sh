#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/migrate_from_previous.sh /path/to/previous/MerchantOS_folder" >&2
  exit 1
fi

SRC="$(cd "$1" && pwd)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/runtime/artifacts" "$ROOT/artifacts"

if [[ -f "$SRC/.env" ]]; then
  cp "$SRC/.env" "$ROOT/.env"
  echo "Copied .env"
else
  echo "WARNING: $SRC/.env not found" >&2
fi

# Pick the richest accessible database instead of blindly preferring a packaged
# top-level DB. Docker builds keep the live state in runtime/merchantos.db.
DB_CHOICE="$(python3 - "$SRC" <<'PY'
from pathlib import Path
import sqlite3, sys
src=Path(sys.argv[1])
candidates=[src/'runtime'/'merchantos.db', src/'merchantos.db']
ranked=[]
for p in candidates:
    if not p.is_file():
        continue
    try:
        con=sqlite3.connect(p)
        def n(table):
            try: return int(con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
            except Exception: return 0
        score=n('events') + 20*n('payment_journeys') + 50*n('decisions') + 100*n('actions') + 100*n('approvals') + n('audit_events')
        ranked.append((score, p))
        con.close()
    except Exception:
        ranked.append((-1,p))
if ranked:
    ranked.sort(key=lambda x:(x[0], str(x[1])), reverse=True)
    print(ranked[0][1])
PY
)"

if [[ -n "${DB_CHOICE:-}" && -f "$DB_CHOICE" ]]; then
  cp "$DB_CHOICE" "$ROOT/merchantos.db"
  cp "$DB_CHOICE" "$ROOT/runtime/merchantos.db"
  echo "Copied operational database from: $DB_CHOICE"
else
  echo "WARNING: no usable merchantos.db found under $SRC" >&2
fi

for file in risknet_hybrid_v2.joblib risknet_hybrid_v2_manifest.json; do
  SOURCE=""
  if [[ -f "$SRC/runtime/artifacts/$file" ]]; then
    SOURCE="$SRC/runtime/artifacts/$file"
  elif [[ -f "$SRC/artifacts/$file" ]]; then
    SOURCE="$SRC/artifacts/$file"
  fi
  if [[ -n "$SOURCE" ]]; then
    cp "$SOURCE" "$ROOT/artifacts/$file"
    cp "$SOURCE" "$ROOT/runtime/artifacts/$file"
    echo "Copied $file from: $SOURCE"
  else
    echo "WARNING: $file not found in source artifacts" >&2
  fi
done

echo "Migration complete. No model retraining was performed."
if [[ -f "$ROOT/runtime/merchantos.db" ]]; then
  MERCHANTOS_DB_PATH="$ROOT/runtime/merchantos.db" MERCHANTOS_ARTIFACT_DIR="$ROOT/runtime/artifacts" python3 "$ROOT/scripts/system_check.py" --state-only || true
fi
