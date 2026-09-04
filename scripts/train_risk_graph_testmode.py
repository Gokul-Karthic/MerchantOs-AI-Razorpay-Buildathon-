from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.ml.risk_model import dataset_readiness, train_testmode_model
from app.services.store import init_db, list_events

init_db()
events = list_events()
print("Dataset readiness:")
print(dataset_readiness(events))
manifest = train_testmode_model(events, activate=True)
print("\nFinalized:", manifest["model_version"])
print("Operational model active:", manifest["active"])
print("Learned calibrator active:", manifest["learned_calibrator_active"])
print("Holdout:", manifest["holdout"])
if manifest["learned_calibrator_rejection_reasons"]:
    print("Calibrator rejected safely:", manifest["learned_calibrator_rejection_reasons"])
print("\nNo additional Razorpay Test Mode payments are required for this model finalization.")
