from __future__ import annotations


def checkout_html() -> str:
    return r'''<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MerchantOS v1.4.1 Razorpay Test Checkout</title>
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <style>
    body{font-family:system-ui,-apple-system,sans-serif;max-width:820px;margin:40px auto;padding:0 20px;background:#f7f8fa;color:#15171a}
    .card{background:white;border:1px solid #e2e5e9;border-radius:16px;padding:24px;margin:16px 0;box-shadow:0 2px 12px rgba(0,0,0,.04)}
    label{display:block;font-weight:650;margin-top:14px} input,select{width:100%;box-sizing:border-box;padding:11px;margin-top:6px;border:1px solid #ccd1d7;border-radius:9px}
    button{margin-top:20px;background:#1d4ed8;color:white;border:0;border-radius:10px;padding:12px 18px;font-weight:700;cursor:pointer}
    pre{white-space:pre-wrap;background:#111827;color:#e5e7eb;padding:14px;border-radius:10px;overflow:auto}.muted{color:#666}.good{color:#137333;font-weight:700}
  </style>
</head>
<body>
  <h1>MerchantOS AI v1.4.1 — Razorpay Test Mode</h1>
  <p class="muted">Every payment created here is a real Razorpay Test Mode transaction. No local synthetic payment generator is used. Controlled labels describe experiments you deliberately run; they never alter Razorpay payment facts.</p>
  <div class="card">
    <label>Amount (INR)</label><input id="amount" type="number" min="1" step="1" value="499" />
    <label>Controlled test label</label>
    <select id="scenario">
      <option>UNLABELED</option><option>NORMAL</option><option>CONTROLLED_ABUSE</option><option>LEGIT_SHARED_NETWORK</option>
    </select>
    <label>Customer reference (optional)</label><input id="customer" placeholder="test-customer-01" />
    <label>Email used in Test Checkout</label><input id="email" value="test@merchantos.local" />
    <label>Contact used in Test Checkout</label><input id="contact" value="9999999999" />
    <button onclick="pay()">Create Razorpay Test Order & Pay</button>
  </div>
  <div class="card"><div id="state">Ready.</div><pre id="output"></pre></div>
<script>
function stableDevice(){let d=localStorage.getItem('merchantos_test_device');if(!d){d=crypto.randomUUID();localStorage.setItem('merchantos_test_device',d)}return d}
async function pay(){
  const out=document.getElementById('output'), state=document.getElementById('state');
  state.textContent='Creating Razorpay Test Mode order…'; out.textContent='';
  const payload={amount_inr:Number(document.getElementById('amount').value),scenario_label:document.getElementById('scenario').value,customer_ref:document.getElementById('customer').value||null,session_id:crypto.randomUUID(),device_id:stableDevice()};
  const r=await fetch('/api/razorpay/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await r.json(); if(!r.ok){state.textContent='Order creation failed';out.textContent=JSON.stringify(data,null,2);return}
  state.textContent='Opening Razorpay Test Checkout…';
  const options={key:data.key_id,amount:data.order.amount,currency:data.order.currency,name:'MerchantOS AI',description:'Razorpay Test Mode transaction',order_id:data.order.id,prefill:{email:document.getElementById('email').value,contact:document.getElementById('contact').value},handler:async function(resp){state.innerHTML='<span class="good">Payment returned from Razorpay Test Checkout. Verifying provider state via API; webhook remains the primary observation…</span>';const sr=await fetch('/api/razorpay/payments/'+resp.razorpay_payment_id+'/sync',{method:'POST'});const sd=await sr.json();out.textContent=JSON.stringify({checkout_response:resp,merchantos_sync:sd},null,2);}};
  const rz=new Razorpay(options);rz.on('payment.failed',async function(resp){state.textContent='Razorpay reported payment failure. Verifying provider state via API; webhook remains primary…';const pid=resp.error&&resp.error.metadata&&resp.error.metadata.payment_id;if(pid){const sr=await fetch('/api/razorpay/payments/'+pid+'/sync',{method:'POST'});out.textContent=JSON.stringify(await sr.json(),null,2)}else{out.textContent=JSON.stringify(resp,null,2)}});rz.open();
}
</script>
</body></html>'''
