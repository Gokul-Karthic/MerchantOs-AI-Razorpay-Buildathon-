from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.ml.payguard import detect_incidents
from app.ml.risk_model import dataset_readiness, model_status
from app.services.guardrails import test_actions_enabled
from app.services.razorpay_client import RazorpayClient
from app.services.store import init_db, list_actions, list_events, verify_audit_chain, webhook_stats

init_db()
events = list_events()
client = RazorpayClient()
print("MerchantOS AI v1.0")
print("Razorpay configured safely:", client.configured)
print("Test Mode key:", client.is_test_mode)
print("Webhooks:", webhook_stats())
print("Test Mode payments:", len(events))
print("PayGuard incidents:", len(detect_incidents(events)))
print("RiskNet readiness:", dataset_readiness(events))
print("RiskNet model:", model_status())
print("Test provider actions enabled:", test_actions_enabled())
print("Actions recorded:", len(list_actions(limit=5000)))
print("Audit chain:", verify_audit_chain())
