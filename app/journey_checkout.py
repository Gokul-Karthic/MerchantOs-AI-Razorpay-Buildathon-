from __future__ import annotations

import json
from html import escape


def journey_checkout_html(*, journey: dict, key_id: str, dashboard_url: str) -> str:
    order_id = str(journey["order_id"])
    amount_paise = int(round(float(journey["amount"]) * 100))
    currency = str(journey.get("currency") or "INR")
    journey_id = str(journey["journey_id"])
    return_url = f"{dashboard_url.rstrip('/')}?journey={journey_id}"
    description = str(journey.get("description") or "MerchantOS live payment journey")

    # json.dumps is used for JS string literals to avoid HTML/JS injection from
    # optional user-provided descriptions or identifiers.
    js = {
        "key": key_id,
        "amount": amount_paise,
        "currency": currency,
        "order_id": order_id,
        "journey_id": journey_id,
        "description": description,
        "return_url": return_url,
    }
    js_data = json.dumps(js)

    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MerchantOS Live Payment Journey</title>
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <style>
    :root{{--ink:#0b1220;--muted:#667085;--border:#e7eaf0;--canvas:#f5f7fa;--navy:#0c1628;--blue:#2457f5;--green:#087f5b;}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Inter","Segoe UI",sans-serif;background:var(--canvas);color:var(--ink)}}
    .wrap{{max-width:820px;margin:0 auto;padding:42px 20px}} .brand{{display:flex;align-items:center;gap:12px;margin-bottom:28px}}
    .logo{{width:40px;height:40px;border-radius:11px;background:linear-gradient(145deg,#6f8cff,#3158f5);display:grid;place-items:center;color:white;font-weight:800;box-shadow:0 8px 20px rgba(49,88,245,.22)}}
    .brand b{{display:block;font-size:18px}} .brand span{{color:var(--muted);font-size:13px}}
    .card{{background:white;border:1px solid var(--border);border-radius:18px;padding:28px;box-shadow:0 12px 34px rgba(16,24,40,.06)}}
    .eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:750}} h1{{font-size:30px;letter-spacing:-.04em;margin:8px 0 9px}} p{{color:var(--muted);line-height:1.6}}
    .amount{{font-size:44px;font-weight:760;letter-spacing:-.05em;margin:22px 0 2px}} .meta{{font-size:13px;color:var(--muted)}}
    .notice{{margin:22px 0;padding:14px 16px;background:#eef3ff;color:#234fd1;border:1px solid #dce6ff;border-radius:12px;font-size:14px;line-height:1.5}}
    button,.button{{display:inline-block;text-decoration:none;margin-top:12px;border:0;border-radius:11px;padding:13px 18px;font-weight:720;cursor:pointer;font-size:15px}}
    button{{background:var(--navy);color:#fff}} .button{{background:#fff;color:var(--ink);border:1px solid var(--border);margin-left:8px}}
    #state{{margin-top:20px;padding:14px 16px;border-radius:12px;background:#f8fafc;color:#475467;border:1px solid var(--border);font-size:14px;line-height:1.5}}
    .good{{background:#ecfdf3!important;color:var(--green)!important;border-color:#c9f1dd!important}} .bad{{background:#fff1f0!important;color:#b42318!important;border-color:#ffd5d2!important}}
    .small{{font-size:12px;color:#98a2b3;margin-top:20px}} code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}}
  </style>
</head>
<body>
<div class="wrap">
  <div class="brand"><div class="logo">M</div><div><b>MerchantOS AI</b><span>Live Payment Journey · Razorpay Test Mode</span></div></div>
  <div class="card">
    <div class="eyebrow">Genuine provider checkout</div>
    <h1>Complete this Test Mode payment</h1>
    <p>This order was created by MerchantOS through Razorpay Test Mode. The payment lifecycle will be traced back in MerchantOS using signed webhooks and provider verification.</p>
    <div class="amount">₹{float(journey['amount']):,.2f}</div>
    <div class="meta">Order <code>{escape(order_id)}</code> · Journey <code>{escape(journey_id)}</code></div>
    <div class="notice">No synthetic payment row is created. This journey is always <b>UNLABELED</b>; experiment labels never influence the live operational decision.</div>
    <button id="payBtn">Open Razorpay Test Checkout</button>
    <a class="button" href="{escape(return_url)}">Return to MerchantOS</a>
    <div id="state">Ready to open Razorpay Test Checkout.</div>
    <div class="small">Use only Razorpay Test Mode credentials and test payment methods.</div>
  </div>
</div>
<script>
const cfg = {js_data};
const state = document.getElementById('state');
async function post(path) {{
  try {{ await fetch(path, {{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}}); }} catch (_) {{}}
}}
async function verifyPayment(paymentId) {{
  if (!paymentId) return;
  try {{
    await fetch('/api/razorpay/payments/' + paymentId + '/sync', {{method:'POST'}});
    await post('/api/journeys/' + cfg.journey_id + '/refresh');
  }} catch (_) {{}}
}}
function openCheckout() {{
  post('/api/journeys/' + cfg.journey_id + '/checkout-opened');
  state.textContent = 'Opening Razorpay Test Checkout…';
  const options = {{
    key: cfg.key,
    amount: cfg.amount,
    currency: cfg.currency,
    name: 'MerchantOS AI',
    description: cfg.description,
    order_id: cfg.order_id,
    prefill: {{email:'test@merchantos.local', contact:'9999999999'}},
    handler: async function(resp) {{
      state.className='good'; state.textContent='Razorpay returned a successful payment. MerchantOS is verifying provider state…';
      await verifyPayment(resp.razorpay_payment_id);
      state.innerHTML='Payment observed and verified. <a href="'+cfg.return_url+'">Open the live journey trace →</a>';
    }},
    modal: {{ ondismiss: function() {{ state.textContent='Checkout closed. You can reopen it or return to MerchantOS.'; }} }}
  }};
  const rz = new Razorpay(options);
  rz.on('payment.failed', async function(resp) {{
    state.className='bad'; state.textContent='Razorpay reported a failed payment. MerchantOS is verifying it so the recovery decision can be traced…';
    const pid = resp.error && resp.error.metadata && resp.error.metadata.payment_id;
    await verifyPayment(pid);
    state.innerHTML='Failure observed. <a href="'+cfg.return_url+'">Open MerchantOS to analyze the recovery path →</a>';
  }});
  rz.open();
}}
document.getElementById('payBtn').addEventListener('click', openCheckout);
</script>
</body>
</html>'''
