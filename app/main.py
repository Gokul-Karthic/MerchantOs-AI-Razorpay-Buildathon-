from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.api.routes import router
from app.test_checkout import checkout_html
from app.journey_checkout import journey_checkout_html
from app.services.razorpay_client import RazorpayClient
from app.services.store import get_journey


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One-time Test-Mode-only finalization from the merchant's existing labeled DB.
    # Once the locked artifact exists, normal startup never refits it.
    from app.services.store import init_db, list_events
    from app.ml.risk_model import ensure_production_model
    init_db()
    ensure_production_model(list_events())
    yield


app = FastAPI(
    title="MerchantOS AI",
    version="1.4.1",
    description=(
        "Razorpay Test Mode-native AI decision layer for merchant operations: "
        "RiskNet Hybrid v2 + PayGuard + Digital Twin + Decision Agent + Guardrails + Verify + Learn."
    ),
    lifespan=lifespan,
)
app.include_router(router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><body style='font-family:system-ui;max-width:860px;margin:50px auto;line-height:1.55'>
    <h1>MerchantOS AI v1.4.1</h1>
    <h3>The AI Decision Layer for Autonomous Merchant Operations</h3>
    <p><b>OBSERVE → UNDERSTAND → SIMULATE → DECIDE → GUARD → ACT → VERIFY → LEARN</b></p>
    <p>Razorpay Test Mode is the only operational transaction source. Live Mode and manual payment injection are blocked.</p>
    <p><b>RiskNet Hybrid v2:</b> fixed production policy + Bayesian entity reputation + optional quality-gated calibrator.</p>
    <ul>
      <li><a href='/test-checkout'>Controlled Test Checkout</a></li>
      <li>Use the Streamlit <b>Live Payment Journey</b> workspace for traceable new payments.</li>
      <li><a href='/docs'>Swagger API</a></li>
      <li><a href='/api/overview'>MerchantOS overview</a></li>
      <li><a href='/api/razorpay/status'>Razorpay status</a></li>
      <li><a href='/api/learning/status'>Learning/readiness status</a></li>
      <li><a href='/api/ml/risk-graph/status'>RiskNet model status</a></li>
      <li><a href='/api/audit/verify'>Audit-chain verification</a></li>
    </ul>
    </body></html>
    """


@app.get("/test-checkout", response_class=HTMLResponse)
def test_checkout():
    return checkout_html()


@app.get("/journey-checkout/{journey_id}", response_class=HTMLResponse)
def journey_checkout(journey_id: str):
    journey = get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="journey not found")
    client = RazorpayClient()
    if not client.configured:
        raise HTTPException(status_code=503, detail="Razorpay Test Mode credentials are not configured")
    dashboard_url = __import__("os").getenv("MERCHANTOS_DASHBOARD_PUBLIC_URL", "http://localhost:8501")
    return journey_checkout_html(journey=journey, key_id=client.key_id, dashboard_url=dashboard_url)
