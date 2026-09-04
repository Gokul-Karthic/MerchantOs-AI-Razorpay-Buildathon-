from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from app.services.razorpay_client import RazorpayClient

client = RazorpayClient()
print("Credentials present:", client.has_credentials)
print("Test-mode key:", client.is_test_mode)
print("Configured safely:", client.configured)
if client.configured:
    data = client.fetch_payments(count=1, skip=0)
    print("Razorpay Test Mode API reachable: yes")
    print("Payments returned:", len(data.get("items", [])))
else:
    print("Razorpay Test Mode API reachable: not checked")
