from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any
import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("MERCHANTOS_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
PUBLIC_API_BASE = os.getenv("MERCHANTOS_PUBLIC_API_URL", "http://127.0.0.1:8000").rstrip("/")
CHECKOUT_URL = f"{PUBLIC_API_BASE}/test-checkout"

st.set_page_config(
    page_title="MerchantOS AI — Operations Console",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------
# Visual system
# -----------------------------
st.markdown(
    """
<style>
:root {
    --mos-ink: #0b1220;
    --mos-ink-2: #172033;
    --mos-muted: #667085;
    --mos-muted-2: #98a2b3;
    --mos-border: #e7eaf0;
    --mos-surface: #ffffff;
    --mos-canvas: #f6f7f9;
    --mos-navy: #0c1628;
    --mos-navy-2: #12203a;
    --mos-blue: #2457f5;
    --mos-blue-soft: #eef3ff;
    --mos-green: #087f5b;
    --mos-green-soft: #ecfdf3;
    --mos-amber: #a15c00;
    --mos-amber-soft: #fff8e7;
    --mos-red: #b42318;
    --mos-red-soft: #fff1f0;
    --mos-purple: #6b4eff;
    --mos-purple-soft: #f3f0ff;
    --mos-shadow: 0 1px 2px rgba(16,24,40,.04), 0 8px 28px rgba(16,24,40,.05);
}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Segoe UI", sans-serif;
    color: var(--mos-ink);
}

.stApp { background: var(--mos-canvas); }

/* Keep Streamlit framework chrome out of the product UI without hiding
   the sidebar reopen control. The header remains transparent so Streamlit
   can mount the collapsed-sidebar control when the navigation is closed. */
[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
    min-height: 0 !important;
}
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* Final-product navigation: keep the sidebar permanently visible on desktop.
   Streamlit 1.48.x collapses the sidebar by translating the entire section
   off-screen. We explicitly neutralize that transform instead of depending
   on Streamlit's version-sensitive collapsed-control DOM. */
[data-testid="stSidebar"],
[data-testid="stSidebar"][aria-expanded="false"],
[data-testid="stSidebar"][aria-expanded="true"] {
    transform: none !important;
    min-width: 286px !important;
    max-width: 286px !important;
    width: 286px !important;
    visibility: visible !important;
    opacity: 1 !important;
    margin-left: 0 !important;
}

[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {
    visibility: visible !important;
    opacity: 1 !important;
}

/* Since the desktop product navigation is intentionally persistent, remove
   Streamlit's collapse affordance. */
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

/* Legacy selectors retained harmlessly for older Streamlit builds. */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: none !important;
}

#MainMenu, footer { display: none !important; }

[data-testid="stSidebar"] {
    min-width: 286px !important;
    max-width: 286px !important;
    width: 286px !important;
    transform: none !important;
}
[data-testid="stSidebar"] > div { width: 286px !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--mos-navy) 0%, #101d33 100%);
    border-right: 0;
}

[data-testid="stSidebar"] > div:first-child { padding-top: 1.35rem; }
[data-testid="stSidebar"] * { color: #f8fafc; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c5cede; }
[data-testid="stSidebar"] .stRadio > label { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: .28rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: .62rem .72rem;
    border-radius: 10px;
    transition: all .14s ease;
    border: 1px solid transparent;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: rgba(255,255,255,.06);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: rgba(255,255,255,.11);
    border-color: rgba(255,255,255,.08);
}
[data-testid="stSidebar"] button {
    border-radius: 10px !important;
    background: rgba(255,255,255,.08) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,.10) !important;
}

.main .block-container {
    max-width: 1460px;
    padding-top: 2.35rem;
    padding-bottom: 3rem;
}

h1, h2, h3, h4 {
    letter-spacing: -.025em;
    color: var(--mos-ink) !important;
}

h1 { font-weight: 720 !important; }
h2, h3 { font-weight: 680 !important; }

.mos-wordmark {
    display: flex;
    align-items: center;
    gap: .72rem;
    margin: 0 .15rem 1.2rem .15rem;
}
.mos-logo {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    background: linear-gradient(145deg, #6f8cff 0%, #3158f5 100%);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.25), 0 6px 16px rgba(30,72,220,.28);
    display: grid;
    place-items: center;
    font-size: 17px;
    font-weight: 800;
    color: white;
}
.mos-wordmark-title { font-size: 1.04rem; font-weight: 750; color: #fff; line-height: 1.05; }
.mos-wordmark-sub { font-size: .72rem; color: #98a8c2; margin-top: .18rem; }

.mos-sidebar-label {
    color: #72839f;
    font-size: .67rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-weight: 700;
    margin: 1.15rem .2rem .35rem;
}

.mos-sidebar-status {
    padding: .8rem .85rem;
    background: rgba(255,255,255,.055);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 12px;
    margin-top: .9rem;
}
.mos-sidebar-status-row {
    display: flex;
    justify-content: space-between;
    gap: .75rem;
    font-size: .76rem;
    color: #c8d2e1;
    margin: .22rem 0;
}
.mos-dot { width: 7px; height: 7px; border-radius: 99px; display: inline-block; margin-right: .4rem; }
.mos-dot.good { background: #42d392; box-shadow: 0 0 0 3px rgba(66,211,146,.10); }
.mos-dot.warn { background: #ffb547; }
.mos-dot.bad { background: #ff6b6b; }

.mos-page-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1.5rem;
    margin-bottom: 1.35rem;
}
.mos-eyebrow {
    color: #667085;
    font-size: .7rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-weight: 750;
    margin-bottom: .38rem;
}
.mos-page-title {
    font-size: 2.02rem;
    line-height: 1.08;
    font-weight: 760;
    letter-spacing: -.038em;
    color: var(--mos-ink);
    margin: 0;
}
.mos-page-subtitle {
    font-size: .97rem;
    color: var(--mos-muted);
    margin-top: .48rem;
    max-width: 780px;
    line-height: 1.55;
}
.mos-badges { display: flex; gap: .4rem; flex-wrap: wrap; justify-content: flex-end; }
.mos-badge {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    border-radius: 999px;
    padding: .3rem .58rem;
    font-size: .7rem;
    line-height: 1;
    font-weight: 700;
    border: 1px solid transparent;
    white-space: nowrap;
}
.mos-badge.good { background: var(--mos-green-soft); color: var(--mos-green); border-color: #c9f1dd; }
.mos-badge.info { background: var(--mos-blue-soft); color: #234fd1; border-color: #dce6ff; }
.mos-badge.warn { background: var(--mos-amber-soft); color: var(--mos-amber); border-color: #fde7ad; }
.mos-badge.bad { background: var(--mos-red-soft); color: var(--mos-red); border-color: #ffd5d2; }
.mos-badge.neutral { background: #f2f4f7; color: #475467; border-color: #e4e7ec; }
.mos-badge.purple { background: var(--mos-purple-soft); color: #5d44d5; border-color: #e0d9ff; }

.mos-kpi {
    min-height: 130px;
    background: var(--mos-surface);
    border: 1px solid var(--mos-border);
    border-radius: 14px;
    padding: 1.03rem 1.08rem .92rem;
    box-shadow: var(--mos-shadow);
}
.mos-kpi-label { color: var(--mos-muted); font-size: .78rem; font-weight: 640; }
.mos-kpi-value { color: var(--mos-ink); font-size: 1.72rem; font-weight: 740; letter-spacing: -.035em; margin-top: .34rem; }
.mos-kpi-help { color: #8b95a5; font-size: .71rem; margin-top: .32rem; line-height: 1.35; }
.mos-kpi-accent { width: 28px; height: 3px; border-radius: 99px; margin-bottom: .72rem; background: #d0d5dd; }
.mos-kpi-accent.good { background: #12a377; }
.mos-kpi-accent.info { background: #3158f5; }
.mos-kpi-accent.warn { background: #df8c13; }
.mos-kpi-accent.bad { background: #d0443d; }
.mos-kpi-accent.purple { background: #6b4eff; }

.mos-card {
    background: var(--mos-surface);
    border: 1px solid var(--mos-border);
    border-radius: 14px;
    padding: 1rem 1.08rem;
    box-shadow: 0 1px 2px rgba(16,24,40,.025);
    margin-bottom: .75rem;
}
.mos-card-title { font-size: .9rem; font-weight: 700; color: var(--mos-ink); }
.mos-card-sub { font-size: .76rem; color: var(--mos-muted); margin-top: .28rem; line-height: 1.45; }
.mos-card-row { display:flex; justify-content:space-between; align-items:center; gap:1rem; }

.mos-section-head { margin-top: 1.7rem; margin-bottom: .72rem; }
.mos-section-title { font-size: 1.05rem; font-weight: 720; color: var(--mos-ink); letter-spacing: -.02em; }
.mos-section-sub { font-size: .78rem; color: var(--mos-muted); margin-top: .2rem; }

.mos-callout {
    border-radius: 13px;
    padding: .88rem 1rem;
    border: 1px solid var(--mos-border);
    background: #fff;
    color: #344054;
    font-size: .81rem;
    line-height: 1.5;
}
.mos-callout.good { background: #f3fff9; border-color: #c8f1dc; }
.mos-callout.info { background: #f5f8ff; border-color: #dce6ff; }
.mos-callout.warn { background: #fffbf1; border-color: #f7e2aa; }
.mos-callout.bad { background: #fff6f5; border-color: #ffd6d2; }

.mos-loop {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: .42rem;
    margin-top: .45rem;
}
.mos-loop-step {
    background: #fff;
    border: 1px solid var(--mos-border);
    border-radius: 11px;
    padding: .68rem .55rem;
    text-align: center;
    color: #475467;
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: .02em;
}
.mos-loop-step.active { border-color: #cfdcff; background: #f7f9ff; color: #244ed2; }

.mos-decision {
    background: #fff;
    border: 1px solid var(--mos-border);
    border-radius: 13px;
    padding: .9rem 1rem;
    margin-bottom: .6rem;
}
.mos-decision-top { display:flex; justify-content:space-between; align-items:center; gap:.7rem; }
.mos-decision-title { font-size: .86rem; font-weight: 700; color: #101828; }
.mos-decision-meta { font-size: .71rem; color: #98a2b3; margin-top: .22rem; }
.mos-decision-reason { font-size: .78rem; color: #667085; margin-top: .55rem; line-height: 1.45; }

.mos-score {
    background: #fff;
    border: 1px solid var(--mos-border);
    border-radius: 15px;
    padding: 1.05rem 1.15rem 1.15rem;
}
.mos-score-value { font-size: 2.15rem; font-weight: 780; letter-spacing: -.045em; }
.mos-score-label { color: var(--mos-muted); font-size: .76rem; }
.mos-score-track { position: relative; height: 10px; background: linear-gradient(90deg,#e5f8f0 0 55%,#fff3d6 55% 64%,#ffe7e4 64% 85%,#ffd4d0 85% 100%); border-radius: 99px; margin-top: .9rem; }
.mos-score-fill { position:absolute; left:0; top:0; bottom:0; background: rgba(16,24,40,.22); border-radius:99px; }
.mos-score-marker { position:absolute; top:-5px; width:2px; height:20px; background:#344054; border-radius:2px; }
.mos-score-scale { display:flex; justify-content:space-between; color:#98a2b3; font-size:.64rem; margin-top:.45rem; }

.mos-twin-option {
    background: #fff;
    border: 1px solid var(--mos-border);
    border-radius: 12px;
    padding: .75rem .9rem;
    margin-bottom: .5rem;
}
.mos-twin-bar { height: 7px; background: #eef1f5; border-radius: 99px; overflow: hidden; margin-top: .55rem; }
.mos-twin-bar > div { height: 100%; background: #3158f5; border-radius: 99px; }

.mos-empty {
    border: 1px dashed #d7dce3;
    border-radius: 13px;
    background: rgba(255,255,255,.55);
    padding: 1.3rem;
    color: #667085;
    font-size: .82rem;
    text-align: center;
}

.mos-hash {
    font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
    font-size: .72rem;
    color: #475467;
    background: #f8fafc;
    border: 1px solid #eaecf0;
    border-radius: 9px;
    padding: .55rem .68rem;
    word-break: break-all;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--mos-border);
    border-radius: 13px;
    overflow: hidden;
    background: #fff;
}

.stButton > button, .stLinkButton > a {
    border-radius: 10px !important;
    min-height: 40px;
    font-weight: 650 !important;
    letter-spacing: -.01em;
}
.stButton > button[kind="primary"] {
    background: #1f4fe0 !important;
    border-color: #1f4fe0 !important;
}

[data-testid="stExpander"] {
    border: 1px solid var(--mos-border) !important;
    border-radius: 12px !important;
    background: #fff;
}

.mos-spotlight {
    background: linear-gradient(145deg,#0d1b31 0%,#14284a 100%);
    color: white;
    border-radius: 16px;
    padding: 1.15rem 1.2rem;
    box-shadow: 0 12px 30px rgba(12,22,40,.12);
}
.mos-spotlight .label { color:#9fb0cc; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.09em; }
.mos-spotlight .value { color:white; font-size:2rem; font-weight:780; letter-spacing:-.04em; margin-top:.3rem; }
.mos-spotlight .sub { color:#c8d2e1; font-size:.78rem; line-height:1.5; margin-top:.3rem; }
.mos-rank { display:inline-flex; align-items:center; border-radius:999px; padding:.24rem .48rem; font-size:.67rem; font-weight:750; margin-right:.45rem; background:#eef3ff; color:#234fd1; border:1px solid #dce6ff; }
.mos-rank.best { background:#ecfdf3; color:#087f5b; border-color:#c9f1dd; }
.mos-activity { background:#fff; border:1px solid var(--mos-border); border-radius:14px; padding:.9rem 1rem; margin-bottom:.6rem; }
.mos-activity-kicker { color:#98a2b3; font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:.07em; }
.mos-activity-title { color:#101828; font-size:.9rem; font-weight:720; margin-top:.24rem; }
.mos-activity-sub { color:#667085; font-size:.75rem; margin-top:.28rem; line-height:1.45; }

@media (max-width: 900px) {
    .mos-page-head { display:block; }
    .mos-badges { justify-content:flex-start; margin-top:.8rem; }
    .mos-loop { grid-template-columns: repeat(2, 1fr); }
}

/* Live Payment Journey */
.mos-journey-hero {
    background: linear-gradient(135deg, #0c1628 0%, #16294a 68%, #244d9c 100%);
    border-radius: 18px;
    padding: 1.25rem 1.35rem;
    color: white;
    box-shadow: 0 16px 34px rgba(12,22,40,.16);
    margin-bottom: 1rem;
}
.mos-journey-hero .label { color: #a9b9d0; font-size: .69rem; text-transform: uppercase; letter-spacing: .1em; font-weight: 760; }
.mos-journey-hero .value { font-size: 1.72rem; font-weight: 770; letter-spacing: -.04em; margin-top: .28rem; }
.mos-journey-hero .sub { color: #cfdaea; font-size: .82rem; margin-top: .38rem; line-height: 1.5; }
.mos-timeline { position: relative; margin: .25rem 0 1.2rem; }
.mos-timeline:before { content:""; position:absolute; left:19px; top:16px; bottom:16px; width:2px; background:#e4e7ec; }
.mos-trace-item { position:relative; padding: .1rem 0 .9rem 3.05rem; }
.mos-trace-dot { position:absolute; left:10px; top:10px; width:20px; height:20px; border-radius:999px; border:5px solid #fff; box-shadow:0 0 0 1px #d0d5dd; background:#98a2b3; z-index:2; }
.mos-trace-dot.good { background:#12a071; box-shadow:0 0 0 1px #92dfc2; }
.mos-trace-dot.bad { background:#d92d20; box-shadow:0 0 0 1px #f8b4ad; }
.mos-trace-dot.warn { background:#f79009; box-shadow:0 0 0 1px #ffd18a; }
.mos-trace-dot.info { background:#3b6df6; box-shadow:0 0 0 1px #b5c7ff; }
.mos-trace-card { background:#fff; border:1px solid var(--mos-border); border-radius:14px; padding:.88rem 1rem; box-shadow:0 1px 2px rgba(16,24,40,.03); }
.mos-trace-top { display:flex; align-items:flex-start; justify-content:space-between; gap:.7rem; }
.mos-trace-stage { color:#667085; font-size:.64rem; text-transform:uppercase; letter-spacing:.11em; font-weight:780; }
.mos-trace-title { font-size:.93rem; font-weight:730; color:var(--mos-ink); margin-top:.18rem; }
.mos-trace-detail { color:#667085; font-size:.81rem; line-height:1.5; margin-top:.35rem; }
.mos-trace-time { color:#98a2b3; font-size:.68rem; white-space:nowrap; }
.mos-status-pill { display:inline-flex; border-radius:999px; padding:.31rem .58rem; font-size:.7rem; font-weight:750; background:#eef3ff; color:#234fd1; }
.mos-live-note { border:1px solid #dce6ff; background:#f5f8ff; color:#344767; border-radius:12px; padding:.78rem .9rem; font-size:.8rem; line-height:1.5; }
/* =========================================================
   FIX: Main-content Streamlit expander text visibility
   ========================================================= */

[data-testid="stMain"] div[data-testid="stExpander"] details > summary {
    background-color: #ffffff !important;
    color: #0f172a !important;
    opacity: 1 !important;
}

[data-testid="stMain"] div[data-testid="stExpander"] details > summary p,
[data-testid="stMain"] div[data-testid="stExpander"] details > summary span,
[data-testid="stMain"] div[data-testid="stExpander"] details > summary div {
    color: #0f172a !important;
    opacity: 1 !important;
}

[data-testid="stMain"] div[data-testid="stExpander"] details > summary svg {
    color: #475569 !important;
    fill: #475569 !important;
    opacity: 1 !important;
}

[data-testid="stMain"] div[data-testid="stExpander"] details {
    border: 1px solid #dbe2ea !important;
    border-radius: 12px !important;
    background: #ffffff !important;
}

[data-testid="stMain"] div[data-testid="stExpander"] details:hover {
    border-color: #c4cfdd !important;
    background: #f8fafc !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# API + formatting helpers
# -----------------------------
SESSION = requests.Session()


def api_get(path: str, default: Any = None, timeout: int = 10):
    try:
        response = SESSION.get(f"{API}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return default


def api_post(path: str, payload: dict[str, Any] | None = None, timeout: int = 40):
    response = SESSION.post(f"{API}{path}", json=payload or {}, timeout=timeout)
    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text or "Request failed"}
    if not response.ok:
        raise RuntimeError(data.get("detail") or "Request failed")
    return data


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def money(value: Any, decimals: int = 0) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    if decimals:
        return f"₹{number:,.{decimals}f}"
    return f"₹{number:,.0f}"


def percent(value: Any, digits: int = 0) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    if abs(number) <= 1.00001:
        number *= 100
    return f"{number:.{digits}f}%"


def compact_id(value: Any, keep: int = 9) -> str:
    text = str(value or "—")
    if len(text) <= keep + 5:
        return text
    return f"{text[:keep]}…{text[-4:]}"


def event_payment_id(event_id: Any) -> str:
    text = str(event_id or "")
    return text.split("rzp-payment:", 1)[-1] if "rzp-payment:" in text else text


def latest_unique(items: list[dict[str, Any]], key: str = "event_id") -> list[dict[str, Any]]:
    """Return the newest operational record per key while preserving audit history elsewhere."""
    ordered = sorted(items or [], key=lambda x: str(x.get("created_at") or ""), reverse=True)
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in ordered:
        value = str(item.get(key) or "")
        if value and value in seen:
            continue
        if value:
            seen.add(value)
        result.append(item)
    return result


def payment_context(event_id: Any) -> dict[str, Any]:
    target = str(event_id or "")
    return next((e for e in events if str(e.get("event_id")) == target), {}) if "events" in globals() else {}


def payment_label(event_id: Any) -> str:
    e = payment_context(event_id)
    amount = money(e.get("amount"), 0) if e else "Payment"
    method = str(e.get("method") or "").replace("_", " ").title() if e else ""
    pid = compact_id(event_payment_id(event_id), 11)
    return f"{amount} · {method} · {pid}" if method else f"{amount} · {pid}"


def human_action(value: Any) -> str:
    return {
        "payment_link": "Send recovery payment link",
        "alternate_method": "Offer a different payment method",
        "retry_same_method": "Retry the same payment method",
        "wait": "Wait and monitor",
        "escalate_review": "Send for human review",
        "monitor": "Monitor",
    }.get(str(value or ""), str(value or "—").replace("_", " ").title())


def human_guardrail(value: Any) -> str:
    return {
        "AUTO_ALLOWED_TEST": "Auto-allowed in Test Mode",
        "APPROVAL_REQUIRED": "Human approval required",
        "BLOCKED": "Blocked / review",
        "SIMULATION_ONLY": "Simulation only",
        "OBSERVATION_ONLY": "Observe only",
    }.get(str(value or ""), str(value or "—").replace("_", " ").title())


def guardrail_tone(value: Any) -> str:
    return {
        "AUTO_ALLOWED_TEST": "good",
        "APPROVAL_REQUIRED": "warn",
        "BLOCKED": "bad",
        "SIMULATION_ONLY": "info",
        "OBSERVATION_ONLY": "neutral",
    }.get(str(value or ""), "neutral")


def risk_tone(score: Any, review: float = 0.64, critical: float = 0.85) -> str:
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= critical:
        return "bad"
    if value >= review:
        return "bad"
    if value >= 0.55:
        return "warn"
    return "good"


def risk_band(score: Any, review: float = 0.64, critical: float = 0.85) -> str:
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= critical:
        return "Critical"
    if value >= review:
        return "Review"
    if value >= 0.55:
        return "Moderate"
    return "Low"


def badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="mos-badge {escape(tone)}">{escape(label)}</span>'


def page_header(eyebrow: str, title: str, subtitle: str, badges: list[tuple[str, str]] | None = None):
    badge_markup = "".join(badge(text, tone) for text, tone in (badges or []))
    st.markdown(
        f"""
<div class="mos-page-head">
  <div>
    <div class="mos-eyebrow">{escape(eyebrow)}</div>
    <div class="mos-page-title">{escape(title)}</div>
    <div class="mos-page-subtitle">{escape(subtitle)}</div>
  </div>
  <div class="mos-badges">{badge_markup}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = ""):
    st.markdown(
        f'<div class="mos-section-head"><div class="mos-section-title">{escape(title)}</div>'
        f'<div class="mos-section-sub">{escape(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str, helper: str = "", tone: str = "info"):
    st.markdown(
        f"""
<div class="mos-kpi">
  <div class="mos-kpi-accent {escape(tone)}"></div>
  <div class="mos-kpi-label">{escape(label)}</div>
  <div class="mos-kpi-value">{escape(value)}</div>
  <div class="mos-kpi-help">{escape(helper)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def callout(text: str, tone: str = "info", title: str | None = None):
    title_html = f'<strong>{escape(title)}</strong><br>' if title else ""
    st.markdown(
        f'<div class="mos-callout {escape(tone)}">{title_html}{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def empty_state(text: str):
    st.markdown(f'<div class="mos-empty">{escape(text)}</div>', unsafe_allow_html=True)


def decision_card(item: dict[str, Any], review_threshold: float = 0.64):
    score = float(item.get("risk_score") or 0)
    status = item.get("guardrail_status") or "SIMULATION_ONLY"
    reason = str(item.get("reason") or "No explanation recorded.")
    payment = event_payment_id(item.get("event_id"))
    action = human_action(item.get("recommended_action"))
    st.markdown(
        f"""
<div class="mos-decision">
  <div class="mos-decision-top">
    <div>
      <div class="mos-decision-title">{escape(action)}</div>
      <div class="mos-decision-meta">{escape(payment_label(item.get("event_id")))} · Risk {escape(percent(score, 0))}</div>
    </div>
    {badge(human_guardrail(status), guardrail_tone(status))}
  </div>
  <div class="mos-decision-reason">{escape(reason)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def risk_meter(score: float, review: float, critical: float):
    score = max(0.0, min(1.0, float(score or 0)))
    review = max(0.0, min(1.0, float(review or 0.64)))
    critical = max(0.0, min(1.0, float(critical or 0.85)))
    band = risk_band(score, review, critical)
    tone = risk_tone(score, review, critical)
    st.markdown(
        f"""
<div class="mos-score">
  <div class="mos-card-row">
    <div>
      <div class="mos-score-label">Merchant risk score</div>
      <div class="mos-score-value">{escape(percent(score, 0))}</div>
    </div>
    {badge(band + " risk", tone)}
  </div>
  <div class="mos-score-track">
    <div class="mos-score-fill" style="width:{score*100:.1f}%"></div>
    <div class="mos-score-marker" style="left:{review*100:.1f}%"></div>
    <div class="mos-score-marker" style="left:{critical*100:.1f}%"></div>
  </div>
  <div class="mos-score-scale"><span>0% · Low</span><span>{review*100:.0f}% · Review</span><span>{critical*100:.0f}% · Critical</span><span>100%</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


# -----------------------------
# Initial data load
# -----------------------------
health = api_get("/health")
if not health:
    st.markdown(
        """
<div style="max-width:760px;margin:12vh auto 0;background:#fff;border:1px solid #e7eaf0;border-radius:18px;padding:2rem;box-shadow:0 12px 35px rgba(16,24,40,.06)">
  <div style="font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;font-weight:750;color:#667085">MerchantOS AI</div>
  <div style="font-size:1.85rem;font-weight:760;letter-spacing:-.035em;margin-top:.45rem">Operations API is not running</div>
  <div style="color:#667085;margin-top:.6rem;line-height:1.55">Start the MerchantOS API, then refresh this page. The dashboard intentionally does not fall back to fabricated or synthetic merchant data.</div>
  <div class="mos-hash" style="margin-top:1rem">python -m uvicorn app.main:app --reload</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.stop()

overview = api_get("/overview", {}) or {}
rzp_status = api_get("/razorpay/status", {}) or {}
events = api_get("/events", []) or []
clusters = api_get("/clusters", []) or []
payguard = api_get("/payguard/status", {}) or {}
payguard_history = api_get("/payguard/incidents?limit=100", []) or []
decisions = api_get("/decisions?limit=100", []) or []
approvals = api_get("/approvals?limit=100", []) or []
actions = api_get("/actions?limit=100", []) or []
learning = api_get("/learning/status", {}) or {}
ml_status = api_get("/ml/status", {}) or {}
audit = api_get("/audit?limit=150", {}) or {}
webhooks = api_get("/razorpay/webhooks?limit=25", {}) or {}
journeys_payload = api_get("/journeys?limit=50", {}) or {}
journeys = journeys_payload.get("items", []) or []

payments_summary = overview.get("payments", {})
revenue_summary = overview.get("revenue", {})
payguard_summary = overview.get("payguard", {})
risk_summary = overview.get("risknet", {})
ops_summary = overview.get("operations", {})
safety_summary = overview.get("safety", {})
model = (ml_status.get("risk_graph", {}) or {}).get("model", {}) or learning.get("risknet_model", {}) or {}
dataset = ml_status.get("dataset", {}) or {}
outcomes = learning.get("operational_outcomes", {}) or {}
audit_chain = audit.get("chain", {}) or {}
review_threshold = float(model.get("review_threshold") or model.get("threshold") or 0.64)
critical_threshold = float(model.get("critical_risk_threshold") or 0.85)
holdout = model.get("holdout", {}) or model.get("test", {}) or {}
test_actions_enabled = as_bool((rzp_status.get("bounded_test_actions") or {}).get("enabled", safety_summary.get("test_actions_enabled", False)))
model_active = bool(model.get("active"))
model_locked = bool(model.get("locked"))
audit_valid = bool(audit_chain.get("valid"))
razorpay_ready = bool(rzp_status.get("configured") and rzp_status.get("test_mode_key"))


# -----------------------------
# Sidebar navigation
# -----------------------------
st.sidebar.markdown(
    """
<div class="mos-wordmark">
  <div class="mos-logo">M</div>
  <div>
    <div class="mos-wordmark-title">MerchantOS AI</div>
    <div class="mos-wordmark-sub">Revenue operations control center</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.sidebar.markdown('<div class="mos-sidebar-label">Workspace</div>', unsafe_allow_html=True)

PAGES = [
    "Overview",
    "Live Payment Journey",
    "Payments",
    "Risk & Trust",
    "Payment Health",
    "Digital Twin",
    "Decisions & Actions",
    "Learning & Outcomes",
    "Audit & Safety",
]
deep_link_journey = str(st.query_params.get("journey") or "").strip()
if deep_link_journey:
    st.session_state["selected_journey_id"] = deep_link_journey
    if st.session_state.get("last_deep_link_journey") != deep_link_journey:
        st.session_state["nav_page"] = "Live Payment Journey"
        st.session_state["last_deep_link_journey"] = deep_link_journey
page = st.sidebar.radio("Navigation", PAGES, label_visibility="collapsed", key="nav_page")

st.sidebar.markdown('<div class="mos-sidebar-label">Environment</div>', unsafe_allow_html=True)
st.sidebar.markdown(
    f"""
<div class="mos-sidebar-status">
  <div class="mos-sidebar-status-row"><span><span class="mos-dot {'good' if razorpay_ready else 'bad'}"></span>Razorpay</span><span>{'Test Mode' if razorpay_ready else 'Needs setup'}</span></div>
  <div class="mos-sidebar-status-row"><span><span class="mos-dot {'good' if model_active else 'warn'}"></span>RiskNet</span><span>{'Active' if model_active else 'Fallback'}</span></div>
  <div class="mos-sidebar-status-row"><span><span class="mos-dot {'good' if audit_valid else 'bad'}"></span>Audit chain</span><span>{'Valid' if audit_valid else 'Check'}</span></div>
  <div class="mos-sidebar-status-row"><span><span class="mos-dot {'warn' if test_actions_enabled else 'good'}"></span>Test actions</span><span>{'Enabled' if test_actions_enabled else 'Off'}</span></div>
</div>
""",
    unsafe_allow_html=True,
)

if st.sidebar.button("Refresh data", use_container_width=True):
    st.rerun()
st.sidebar.caption(f"Core {health.get('version', '—')} · Updated {datetime.now().strftime('%H:%M:%S')}")

GLOBAL_BADGES = [
    ("Test Mode", "info" if razorpay_ready else "bad"),
    ("Risk controls active", "good" if model_active else "warn"),
    ("Audit verified", "good" if audit_valid else "bad"),
]


# -----------------------------
# Overview
# -----------------------------
if page == "Overview":
    page_header(
        "Executive view",
        "Revenue operations, explained simply",
        "MerchantOS watches payment health, assesses risk, compares recovery options, and applies guardrails before any Test Mode action is allowed.",
        [("Operations healthy", "good" if audit_valid and model_active and razorpay_ready else "warn")],
    )

    recovered = float(revenue_summary.get("verified_recovered_inr") or outcomes.get("actual_recovery_inr") or 0)
    failed_value = float(revenue_summary.get("failed_value_inr") or 0)
    active_incidents = int(payguard_summary.get("active_incidents") or 0)
    latest_pending = latest_unique([a for a in approvals if a.get("status") == "PENDING"], "event_id")
    pending_approvals = len(latest_pending)
    recovered_actions = int(outcomes.get("recovered_actions") or sum(a.get("status") == "VERIFIED_RECOVERED" for a in actions))
    action_count = int(outcomes.get("actions_total") or len(actions))

    cols = st.columns(4)
    with cols[0]:
        kpi("Verified revenue recovered", money(recovered), "Provider-verified revenue recovered through guarded Test Mode actions.", "good")
    with cols[1]:
        kpi("Failed payment value", money(failed_value), "Value represented by failed Test Mode payments currently known to MerchantOS.", "warn")
    with cols[2]:
        kpi("Successful recoveries", f"{recovered_actions} / {action_count}", "Verified recoveries compared with all bounded provider actions.", "info")
    with cols[3]:
        kpi("Needs attention", str(active_incidents + pending_approvals), f"{active_incidents} payment-health incident(s) · {pending_approvals} unique payment approval(s).", "purple" if active_incidents + pending_approvals else "good")

    section("How MerchantOS works", "Every provider action passes through an explicit safety boundary. Audit records the whole loop.")
    st.markdown(
        '<div class="mos-loop">'
        '<div class="mos-loop-step active">1 · Observe</div>'
        '<div class="mos-loop-step active">2 · Understand</div>'
        '<div class="mos-loop-step active">3 · Simulate</div>'
        '<div class="mos-loop-step active">4 · Decide</div>'
        '<div class="mos-loop-step active">5 · Guard</div>'
        '<div class="mos-loop-step active">6 · Act</div>'
        '<div class="mos-loop-step active">7 · Verify</div>'
        '<div class="mos-loop-step active">8 · Learn</div>'
        '</div><div style="font-size:.7rem;color:#98a2b3;margin-top:.45rem;text-align:right">Audit is continuous across every step.</div>',
        unsafe_allow_html=True,
    )

    latest_decisions = latest_unique(decisions, "event_id")
    latest_recovered = next((a for a in sorted(actions, key=lambda x: str(x.get("verified_at") or x.get("created_at") or ""), reverse=True) if a.get("status") == "VERIFIED_RECOVERED"), None)
    latest_blocked = next((d for d in latest_decisions if d.get("guardrail_status") == "BLOCKED" and float(d.get("risk_score") or 0) >= review_threshold), None)
    latest_sim = next((d for d in latest_decisions if d.get("guardrail_status") == "SIMULATION_ONLY"), None)

    left, right = st.columns([1.05, .95], gap="large")
    with left:
        section("Recent activity", "Three examples show how MerchantOS can recover, review, or simulate depending on the evidence.")
        shown = 0
        if latest_recovered:
            exp = float(latest_recovered.get("expected_recovery") or 0)
            act = float(latest_recovered.get("actual_recovery") or 0)
            lift = ((act / exp) - 1) * 100 if exp > 0 else 0
            prefix = "+" if lift >= 0 else ""
            st.markdown(
                f'<div class="mos-activity"><div class="mos-activity-kicker">Verified recovery</div><div class="mos-activity-title">{escape(money(act,2))} recovered through a guarded Payment Link</div><div class="mos-activity-sub">Expected {escape(money(exp,2))} · {prefix}{lift:.0f}% vs expected · {escape(payment_label(latest_recovered.get("event_id")))}</div></div>',
                unsafe_allow_html=True,
            )
            shown += 1
        if latest_blocked:
            st.markdown(
                f'<div class="mos-activity"><div class="mos-activity-kicker">Risk review</div><div class="mos-activity-title">Recovery automation suppressed at {escape(percent(latest_blocked.get("risk_score"),0))} risk</div><div class="mos-activity-sub">{escape(payment_label(latest_blocked.get("event_id")))} · MerchantOS routed the payment to review instead of executing a provider action.</div></div>',
                unsafe_allow_html=True,
            )
            shown += 1
        if latest_sim:
            st.markdown(
                f'<div class="mos-activity"><div class="mos-activity-kicker">Simulation</div><div class="mos-activity-title">{escape(human_action(latest_sim.get("recommended_action")))}</div><div class="mos-activity-sub">{escape(payment_label(latest_sim.get("event_id")))} · Risk {escape(percent(latest_sim.get("risk_score"),0))} · No provider action executed.</div></div>',
                unsafe_allow_html=True,
            )
            shown += 1
        if not shown:
            empty_state("Recent operational activity will appear after MerchantOS evaluates failed Test Mode payments.")

    with right:
        section("Business impact", "Verified outcomes are compared with what MerchantOS expected before acting.")
        expected = float(outcomes.get("expected_recovery_inr") or 0)
        actual = float(outcomes.get("actual_recovery_inr") or recovered)
        ratio = float(outcomes.get("realized_vs_expected_ratio") or 0)
        st.markdown(
            f'<div class="mos-spotlight"><div class="label">Recovery performance</div><div class="value">{ratio:.2f}×</div><div class="sub">Actual versus expected recovery across executed actions.<br><strong>{escape(money(actual,2))}</strong> verified · {escape(money(expected,2))} expected</div></div>',
            unsafe_allow_html=True,
        )

        section("Safety posture", "MerchantOS exposes one bounded provider action and blocks unsafe shortcuts.")
        safety_rows = [
            ("Allowed provider action", "Test Mode Payment Links" if test_actions_enabled else "Disabled", "warn" if test_actions_enabled else "neutral"),
            ("Live Mode", "Blocked", "good"),
            ("Model direct execution", "Blocked", "good"),
            ("Synthetic financial inputs", "Blocked", "good"),
            ("Manual fake payments", "Blocked", "good"),
        ]
        for name, value, tone in safety_rows:
            st.markdown(
                f'<div class="mos-card"><div class="mos-card-row"><div class="mos-card-title">{escape(name)}</div>{badge(value, tone)}</div></div>',
                unsafe_allow_html=True,
            )

# -----------------------------
# Live Payment Journey
# -----------------------------
elif page == "Live Payment Journey":
    page_header(
        "Live demo · Razorpay Test Mode",
        "Live Payment Journey",
        "Create a genuine Razorpay Test Mode payment through MerchantOS and follow its lifetime from order creation to risk, simulation, decision, guarded action, verification, learning, and audit.",
        [("No synthetic payments", "good"), ("Live Mode blocked", "good")],
    )

    create_col, trace_col = st.columns([.82, 1.18], gap="large")
    with create_col:
        section("Start a new payment", "This creates a real Razorpay Test Mode order. Live journey payments are always UNLABELED so experiment labels cannot influence the decision.")
        with st.form("journey_create_form", clear_on_submit=False):
            amount_inr = st.number_input("Amount (INR)", min_value=1.0, max_value=1_000_000.0, value=499.0, step=1.0)
            customer_ref = st.text_input("Customer reference (optional)", placeholder="demo-customer-01")
            description = st.text_input("Description (optional)", value="MerchantOS live payment journey")
            submitted = st.form_submit_button("Create Test Mode payment", use_container_width=True, type="primary")
        if submitted:
            try:
                created = api_post(
                    "/journeys",
                    {
                        "amount_inr": float(amount_inr),
                        "customer_ref": customer_ref.strip() or None,
                        "description": description.strip() or None,
                    },
                )
                jid = (created.get("journey") or {}).get("journey_id")
                if jid:
                    st.session_state["selected_journey_id"] = jid
                    st.query_params["journey"] = jid
                    st.success("Razorpay Test Mode order created. Open checkout to continue the journey.")
                    st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

        st.markdown(
            '<div class="mos-live-note"><strong>What this proves:</strong> MerchantOS is not inserting a fake payment into its database. Razorpay creates the order and payment; MerchantOS observes the provider lifecycle and adds intelligence around it.</div>',
            unsafe_allow_html=True,
        )

    with trace_col:
        section("Journey workspace", "Select an existing live journey or create a new one. Use Refresh after completing Razorpay checkout if a webhook has not arrived yet.")
        if not journeys:
            empty_state("No live payment journeys yet. Create one on the left to begin.")
            selected_journey_id = None
        else:
            journey_map = {str(item.get("journey_id")): item for item in journeys}
            choice_ids = list(journey_map.keys())
            preferred = str(st.session_state.get("selected_journey_id") or "")
            initial = choice_ids.index(preferred) if preferred in choice_ids else 0

            def _journey_option(jid: str) -> str:
                item = journey_map[jid]
                return f"{money(item.get('amount'), 0)} · {str(item.get('status') or 'AWAITING_PAYMENT').replace('_',' ').title()} · {compact_id(jid, 12)}"

            selected_journey_id = st.selectbox(
                "Live journey",
                choice_ids,
                index=initial,
                format_func=_journey_option,
                label_visibility="collapsed",
            )
            st.session_state["selected_journey_id"] = selected_journey_id
            st.query_params["journey"] = selected_journey_id

    if selected_journey_id:
        trace = api_get(f"/journeys/{selected_journey_id}", {}) or {}
        journey = trace.get("journey", {}) or {}
        payment = trace.get("payment", {}) or {}
        risk = trace.get("risk", {}) or {}
        decision = trace.get("decision", {}) or {}
        trace_actions = trace.get("actions", []) or []
        status = str(trace.get("status") or journey.get("status") or "AWAITING_PAYMENT")
        risk_score = risk.get("risk_score")
        payment_id = payment.get("payment_id")
        checkout_url = f"{PUBLIC_API_BASE}/journey-checkout/{selected_journey_id}"

        st.markdown(
            f'''<div class="mos-journey-hero">
              <div class="label">Current live journey</div>
              <div class="value">{escape(money(journey.get('amount'), 2))} · {escape(status.replace('_',' ').title())}</div>
              <div class="sub">Journey {escape(compact_id(selected_journey_id, 16))} · Order {escape(compact_id(journey.get('order_id'), 16))} · Payment {escape(compact_id(payment_id, 16) if payment_id else 'not observed yet')}</div>
            </div>''',
            unsafe_allow_html=True,
        )

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi("Provider state", str(payment.get("event_type") or status).replace("payment.", "").replace("_", " ").title(), "Latest Razorpay state known to MerchantOS.", "good" if payment.get("event_type") == "payment.captured" else "warn" if payment.get("event_type") == "payment.failed" else "info")
        with k2:
            kpi("Risk", percent(risk_score, 0) if risk_score is not None else "Pending", f"Review begins at {review_threshold*100:.0f}%.", risk_tone(risk_score or 0, review_threshold, critical_threshold) if risk_score is not None else "neutral")
        with k3:
            payment_event_type = str(payment.get("event_type") or "")

            if decision:
                kpi(
                    "Decision",
                    human_action(decision.get("recommended_action")),
                    human_guardrail(decision.get("guardrail_status")),
                    guardrail_tone(decision.get("guardrail_status")),
                )

            elif payment_event_type in {"payment.captured", "payment.authorized"}:
                kpi(
                    "Decision",
                    "No recovery needed",
                    "The original Razorpay payment succeeded, so MerchantOS correctly avoided creating a recovery action.",
                    "good",
                )

            elif payment_event_type == "payment.failed":
                kpi(
                    "Decision",
                    "Ready to analyze",
                    "Run recovery analysis to compare interventions and apply guardrails.",
                    "warn",
                )

            else:
                kpi(
                    "Decision",
                    "Waiting",
                    "MerchantOS is waiting for a Razorpay payment outcome.",
                    "neutral",
                )

        with k4:
            recovered_value = sum(float(action.get("actual_recovery") or 0) for action in trace_actions)
            kpi("Verified recovery", money(recovered_value, 2), "Actual recovery verified from Razorpay provider state.", "good" if recovered_value else "neutral")

        payment_event_type = str(payment.get("event_type") or "")
        is_failed_payment = payment_event_type == "payment.failed"
        is_successful_payment = payment_event_type in {
            "payment.captured",
            "payment.authorized",
        }

        controls = st.columns([1, 1, 1, 1.25], gap="small")

        with controls[0]:
            st.link_button(
                "Open Razorpay checkout",
                checkout_url,
                use_container_width=True,
            )

        with controls[1]:
            if st.button("Refresh from Razorpay", use_container_width=True):
                try:
                    api_post(f"/journeys/{selected_journey_id}/refresh")
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

        with controls[2]:
            if is_successful_payment:
                analyze_label = "No recovery needed"
            elif is_failed_payment:
                analyze_label = "Analyze & decide"
            else:
                analyze_label = "Waiting for payment"

            if st.button(
                analyze_label,
                use_container_width=True,
                disabled=not is_failed_payment,
            ):
                try:
                    api_post(
                        f"/journeys/{selected_journey_id}/analyze",
                        {
                            "auto_execute_test_action": False,
                            "force_redecide": False,
                        },
                    )
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

        with controls[3]:
            if not test_actions_enabled:
                bounded_label = "Test actions disabled"
            elif is_successful_payment:
                bounded_label = "Payment already successful"
            elif is_failed_payment:
                bounded_label = "Analyze + bounded Test action"
            else:
                bounded_label = "Waiting for failed payment"

            if st.button(
                bounded_label,
                use_container_width=True,
                disabled=(not is_failed_payment or not test_actions_enabled),
            ):
                try:
                    api_post(
                        f"/journeys/{selected_journey_id}/analyze",
                        {
                            "auto_execute_test_action": True,
                            # Reuse the existing payment decision.
                            # Do not create another decision just
                            # because the ACT button was clicked again.
                            "force_redecide": False,
                        },
                    )
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))


        if trace_actions:
            newest_action = sorted(trace_actions, key=lambda x: str(x.get("created_at") or ""), reverse=True)[0]
            link = (newest_action.get("provider_payload") or {}).get("short_url")
            a1, a2 = st.columns([1.4, .6])
            with a1:
                st.markdown(
                    f'<div class="mos-card"><div class="mos-card-row"><div><div class="mos-card-title">Recovery action</div><div class="mos-card-sub">{escape(str(newest_action.get("status") or "—").replace("_"," ").title())} · Expected {escape(money(newest_action.get("expected_recovery"),2))} · Actual {escape(money(newest_action.get("actual_recovery"),2))}</div></div>{badge("Razorpay Test Mode", "info")}</div></div>',
                    unsafe_allow_html=True,
                )
                if link:
                    st.link_button("Open recovery Payment Link", link, use_container_width=True)
            with a2:
                if st.button("Verify recovery", use_container_width=True):
                    try:
                        api_post(f"/journeys/{selected_journey_id}/verify")
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))

        section("Payment lifetime", "A single chronological trace across Razorpay observations and MerchantOS intelligence. Audit remains continuous behind every stage.")
        timeline = trace.get("timeline", []) or []
        if timeline:
            html = ['<div class="mos-timeline">']
            for item in timeline:
                raw_at = str(item.get("at") or "")
                try:
                    dt = pd.to_datetime(raw_at, utc=True)
                    when = dt.strftime("%d %b · %H:%M:%S")
                except Exception:
                    when = raw_at
                tone = str(item.get("tone") or "info")
                html.append(
                    f'''<div class="mos-trace-item">
                      <div class="mos-trace-dot {escape(tone)}"></div>
                      <div class="mos-trace-card">
                        <div class="mos-trace-top"><div><div class="mos-trace-stage">{escape(str(item.get('stage') or 'TRACE'))} · {escape(str(item.get('source') or 'MerchantOS'))}</div><div class="mos-trace-title">{escape(str(item.get('title') or 'Event'))}</div></div><div class="mos-trace-time">{escape(when)}</div></div>
                        <div class="mos-trace-detail">{escape(str(item.get('detail') or ''))}</div>
                      </div>
                    </div>'''
                )
            html.append('</div>')
            st.markdown("".join(html), unsafe_allow_html=True)
        else:
            empty_state("The payment lifetime will populate as Razorpay and MerchantOS events occur.")

        if trace.get("digital_twin"):
            section("Decision trace", "For failed payments, MerchantOS compares bounded interventions before a recommendation reaches Guardrails.")
            twin = sorted(trace.get("digital_twin") or [], key=lambda x: float(x.get("expected_net_value_inr") or -1e18), reverse=True)
            twin_df = pd.DataFrame([
                {
                    "Rank": idx + 1,
                    "Intervention": human_action(item.get("action")),
                    "Recovery probability": percent(item.get("expected_recovery_probability"), 0),
                    "Expected recovery": money(item.get("expected_recovery_inr"), 2),
                    "Risk penalty": money(item.get("risk_penalty_inr"), 2),
                    "Expected net value": money(item.get("expected_net_value_inr"), 2),
                    "Operational risk": str(item.get("operational_risk") or "—").title(),
                }
                for idx, item in enumerate(twin)
            ])
            st.dataframe(twin_df, hide_index=True, use_container_width=True)

        with st.expander("Technical trace evidence"):
            st.json({
                "journey": journey,
                "payment": payment,
                "risk": risk,
                "payguard_incident": trace.get("payguard_incident"),
                "decision": decision,
                "approvals": trace.get("approvals"),
                "actions": trace_actions,
                "webhooks": trace.get("webhooks"),
                "audit": trace.get("audit"),
                "safety": trace.get("safety"),
            })


# -----------------------------
# Payments
# -----------------------------
elif page == "Payments":

    page_header(
        "Observe",
        "Payments & ingestion",
        "See what MerchantOS actually observed from Razorpay Test Mode. Signed webhooks are primary; API sync is used only for verification and backfill.",
        [("Razorpay Test Mode", "info" if razorpay_ready else "bad")],
    )

    webhook_stats = webhooks.get("stats", {}) if isinstance(webhooks, dict) else {}
    cols = st.columns(4)
    with cols[0]:
        kpi("Observed payments", str(payments_summary.get("total", len(events))), "All ingested Test Mode payment events.", "info")
    with cols[1]:
        kpi("Captured", str(payments_summary.get("captured", sum(e.get("event_type") == "payment.captured" for e in events))), "Successful captured payment observations.", "good")
    with cols[2]:
        kpi("Failed", str(payments_summary.get("failed", sum(e.get("event_type") == "payment.failed" for e in events))), "Failed payments available for recovery analysis.", "warn")
    with cols[3]:
        processed = webhook_stats.get("processed") or webhook_stats.get("processed_events") or 0
        kpi("Verified webhooks", str(processed), "Signed webhook deliveries processed by MerchantOS.", "purple")

    section("Razorpay connection", "A quick check that the data pipeline is authentic and safely restricted to Test Mode.")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        callout("Connected to a Test Mode key." if razorpay_ready else "Razorpay Test Mode needs configuration.", "good" if razorpay_ready else "bad", "Provider mode")
    with c2:
        callout("Signed webhook is the primary source of truth." if rzp_status.get("webhook_secret_configured") else "Webhook secret is not configured.", "good" if rzp_status.get("webhook_secret_configured") else "warn", "Ingestion")
    with c3:
        callout("Manual event injection is disabled by policy.", "good", "Data integrity")

    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        st.link_button("Open Test Checkout", CHECKOUT_URL, use_container_width=True)
    with b2:
        if st.button("Verify / backfill from Razorpay", use_container_width=True):
            try:
                result = api_post("/razorpay/sync", {"count": 100, "skip": 0}, timeout=45)
                st.success(f"Provider sync completed. {result.get('fetched', result.get('synced', 'Latest'))} records checked.")
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))

    section("Payment activity", "Operational fields only. Experiment labels are intentionally kept out of the main merchant view.")
    if events:
        df = pd.DataFrame(events).copy()
        if "timestamp" in df.columns:
            df["Time"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%d %b · %H:%M")
        else:
            df["Time"] = "—"
        df["Result"] = df.get("event_type", pd.Series(dtype=str)).map({"payment.captured": "Captured", "payment.failed": "Failed", "payment.authorized": "Authorized"}).fillna(df.get("event_type", "—"))
        df["Amount"] = df.get("amount", 0).map(lambda x: money(x, 2))
        df["Payment"] = df.get("payment_id", pd.Series(dtype=str)).map(lambda x: compact_id(x, 12))
        df["Method"] = df.get("method", "unknown").astype(str).str.replace("_", " ").str.title()
        df["Bank"] = df.get("bank", "unknown").replace({"unknown": "—"})
        df["Customer"] = df.get("customer_id", pd.Series(dtype=str)).map(lambda x: compact_id(x, 10))

        method_options = ["All"] + sorted({str(v).title() for v in df["Method"].dropna().unique()})
        f1, f2 = st.columns(2)
        with f1:
            result_filter = st.selectbox("Result", ["All", "Failed", "Captured", "Authorized"], key="payment_result")
        with f2:
            method_filter = st.selectbox("Payment method", method_options, key="payment_method")
        view = df
        if result_filter != "All":
            view = view[view["Result"] == result_filter]
        if method_filter != "All":
            view = view[view["Method"] == method_filter]
        st.dataframe(
            view[["Time", "Result", "Amount", "Payment", "Method", "Bank", "Customer"]],
            use_container_width=True,
            hide_index=True,
            height=420,
        )
    else:
        empty_state("No Test Mode payments have been ingested yet. Use the Test Checkout or send a real Razorpay Test Mode payment through the configured webhook.")

    with st.expander("Technical ingestion evidence"):
        st.caption("This section is for technical reviewers. It is not required to understand day-to-day merchant operations.")
        st.json({"razorpay": rzp_status, "webhook_stats": webhook_stats})
        labels = dataset.get("scenario_labels", {}) or {}
        if labels:
            st.markdown("**Offline evaluation labels**")
            st.caption("These labels are controlled Test Mode experiment metadata used for training/evaluation only. The operational policy explicitly prevents them from influencing the current decision.")
            st.dataframe(pd.DataFrame([{"Label": k, "Count": v} for k, v in labels.items()]), hide_index=True, use_container_width=True)


# -----------------------------
# Risk & Trust
# -----------------------------
elif page == "Risk & Trust":
    page_header(
        "Understand",
        "Risk & trust",
        "RiskNet helps MerchantOS avoid recovering money in a way that could amplify suspicious behavior. The model cannot execute provider actions directly.",
        [("Validated model", "good" if model.get("learned_calibrator_quality_gate_passed") else "warn")],
    )

    cols = st.columns(4)
    with cols[0]:
        kpi("Risk controls", "Active" if model_active else "Fallback", "RiskNet contributes evidence but can never execute a provider action directly.", "good" if model_active else "warn")
    with cols[1]:
        kpi("Review begins", percent(review_threshold, 0), "Payments at or above this risk level are routed to human review.", "warn")
    with cols[2]:
        kpi("Critical risk", percent(critical_threshold, 0), "Very-high-risk payments are treated as critical cases.", "bad")
    with cols[3]:
        kpi("Model quality check", "Passed" if model.get("learned_calibrator_quality_gate_passed") else "Fallback", f"Holdout ROC-AUC {float(holdout.get('roc_auc') or 0):.3f} · PR-AUC {float(holdout.get('pr_auc') or 0):.3f}.", "good" if model.get("learned_calibrator_quality_gate_passed") else "warn")

    if model.get("learned_calibrator_quality_gate_passed"):
        callout("The learned calibrator passed its quality gate. MerchantOS combines it with the fixed behavioral and Bayesian reputation layers.", "good", "Validated model")
    else:
        callout("The learned calibrator did not pass the quality gate. MerchantOS is operating on the fixed policy + Bayesian reputation layers instead.", "warn", "Safe fallback")

    section("Inspect a payment", "Choose any observed payment to see the risk score, model components, and the evidence MerchantOS can explain.")
    if events:
        event_lookup: dict[str, str] = {}
        for e in events:
            label = f"{e.get('payment_id') or compact_id(e.get('event_id'), 14)} · {money(e.get('amount'), 0)} · {str(e.get('method') or 'unknown').title()} · {str(e.get('event_type') or '').replace('payment.', '').title()}"
            event_lookup[label] = e.get("event_id")
        selected_label = st.selectbox("Payment", list(event_lookup.keys()), label_visibility="collapsed")
        selected_event_id = event_lookup[selected_label]
        risk_detail = api_get(f"/ml/risk-graph/score/{selected_event_id}", {}) or {}
        if risk_detail:
            left, right = st.columns([1, 1], gap="large")
            with left:
                score = float(risk_detail.get("risk_score") or 0)
                risk_meter(score, float(risk_detail.get("review_threshold") or review_threshold), float(risk_detail.get("critical_risk_threshold") or critical_threshold))
                st.caption("A score is decision evidence, not a payment outcome prediction. RiskNet never executes a Razorpay action directly.")
            with right:
                c1, c2 = st.columns(2)
                with c1:
                    kpi("Behavior + reputation", percent(risk_detail.get('deterministic_risk_score'), 0), "Fixed behavioral and Bayesian reputation evidence.", "info")
                with c2:
                    learned = risk_detail.get("learned_risk_score")
                    kpi("Validated ML signal", "—" if learned is None else percent(learned, 0), "Learned signal admitted only after the holdout quality gate passed.", "purple")
                status_text = "Review required" if risk_detail.get("flagged_for_review") else "No RiskNet review required"
                callout(status_text, "bad" if risk_detail.get("flagged_for_review") else "good", "Operational result")

            evidence = risk_detail.get("feature_evidence", []) or []
            if evidence:
                section("Explainable evidence", "Investigation signals are visible even when unreliable local identity fields are suppressed from learned scoring.")
                for item in evidence:
                    st.markdown(f'<div class="mos-card"><div class="mos-card-title">{escape(str(item))}</div></div>', unsafe_allow_html=True)
        else:
            empty_state("Risk details are unavailable for this payment.")
    else:
        empty_state("Risk inspection becomes available after Razorpay Test Mode payments are ingested.")

    identity = model.get("identity_quality", {}) or {}
    section("Identity quality guard", "MerchantOS automatically ignores collapsed local device/IP identity as learned-model input instead of pretending it is useful evidence.")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi("Unique customers", str(identity.get("unique_customers", "—")), "Customers represented in the controlled Test Mode dataset.", "info")
    with c2:
        kpi("Device signal", "Suppressed" if not identity.get("device_features_allowed", True) else "Allowed", "Suppressed because local browser identity did not provide credible diversity." if not identity.get("device_features_allowed", True) else "Identity diversity passed the reliability check.", "good")
    with c3:
        kpi("IP signal", "Suppressed" if not identity.get("ip_features_allowed", True) else "Allowed", "Suppressed because localhost/network identity did not provide credible diversity." if not identity.get("ip_features_allowed", True) else "Identity diversity passed the reliability check.", "good")

    section("Risk graph", "Shared entities are shown as investigation context, not as an automatic action trigger.")
    if clusters:
        top_clusters = sorted(clusters, key=lambda c: float(c.get("estimated_exposure") or 0), reverse=True)[:4]
        cluster_cols = st.columns(min(2, len(top_clusters))) if top_clusters else []
        for idx, cluster in enumerate(top_clusters):
            with cluster_cols[idx % len(cluster_cols)]:
                cluster_risk = float(cluster.get("risk_score") or 0)
                members = int(cluster.get("members") or 0)
                exposure = money(cluster.get("estimated_exposure"), 0)
                state = str(cluster.get("classification") or "Monitor").replace("_", " ").title()
                st.markdown(
                    f'<div class="mos-card"><div class="mos-card-row"><div><div class="mos-card-title">{escape(state)} cluster</div><div class="mos-card-sub">{members} linked observations · {escape(exposure)} exposure</div></div>{badge(percent(cluster_risk,0) + " risk", risk_tone(cluster_risk, review_threshold, critical_threshold))}</div></div>',
                    unsafe_allow_html=True,
                )
        with st.expander("Technical graph details"):
            cdf = pd.DataFrame(clusters)
            view = pd.DataFrame({
                "Cluster": cdf.get("cluster_id", "—").map(lambda x: compact_id(x, 14)),
                "Classification": cdf.get("classification", "—").astype(str).str.replace("_", " ").str.title(),
                "Risk": cdf.get("risk_score", 0).map(lambda x: percent(x, 0)),
                "Members": cdf.get("members", 0),
                "Exposure": cdf.get("estimated_exposure", 0).map(lambda x: money(x, 0)),
                "Recommended": cdf.get("recommended_action", "—").astype(str).str.replace("_", " ").str.title(),
            })
            st.dataframe(view, hide_index=True, use_container_width=True, height=300)
            cluster_ids = [c.get("cluster_id") for c in clusters if c.get("cluster_id")]
            selected_cluster = st.selectbox("Inspect cluster evidence", cluster_ids, key="cluster_select") if cluster_ids else None
            if selected_cluster:
                cluster = next((c for c in clusters if c.get("cluster_id") == selected_cluster), {})
                for line in (cluster.get("evidence") or []) + (cluster.get("validation_reasons") or []):
                    st.write(f"• {line}")
    else:
        empty_state("No multi-payment graph cluster currently meets the display criteria.")

    with st.expander("Technical model card"):
        st.json(model)


# -----------------------------
# PayGuard
# -----------------------------
elif page == "Payment Health":
    page_header(
        "Understand",
        "Payment health",
        "PayGuard looks for sudden payment-method or bank degradation so MerchantOS can distinguish a customer problem from a provider-route problem.",
        [("No active degradation", "good") if not (payguard.get("incidents", []) or []) else ("Active degradation", "bad")],
    )

    incidents = payguard.get("incidents", []) or []
    active_rar = float(sum(float(i.get("revenue_at_risk") or 0) for i in incidents))
    high_count = sum(str(i.get("severity", "")).lower() in {"high", "critical"} for i in incidents)
    cols = st.columns(4)
    with cols[0]:
        kpi("Active incidents", str(len(incidents)), "Current method/bank degradations meeting PayGuard evidence thresholds.", "bad" if incidents else "good")
    with cols[1]:
        kpi("Revenue at risk", money(active_rar), "Estimated payment value exposed to currently detected degradation.", "warn" if active_rar else "good")
    with cols[2]:
        kpi("High severity", str(high_count), "Incidents that deserve immediate operator attention.", "bad" if high_count else "good")
    with cols[3]:
        kpi("Historical incidents", str(len(payguard_history)), "Saved incident lifecycle records for audit and review.", "info")

    c1, _ = st.columns([1, 3])
    with c1:
        if st.button(
            "Run PayGuard analysis",
            type="primary",
            use_container_width=True,
        ):
            try:
                result = api_post("/payguard/analyze")

                st.session_state[
                    "payguard_last_analysis"
                ] = result

                st.rerun()

            except RuntimeError as exc:
                st.error(str(exc))

    payguard_feedback = st.session_state.get(
        "payguard_last_analysis"
    )

    if payguard_feedback is not None:

        detected = int(
            payguard_feedback.get(
                "detected",
                0,
            )
            or 0
        )

        if detected:
            st.success(
                f"PayGuard analysis complete · "
                f"{detected} active payment-route "
                f"degradation incident(s) detected."
            )
        else:
            st.info(
                "PayGuard analysis complete · "
                "no payment route currently meets the "
                "active-degradation threshold. "
                "The observed route evidence is shown below."
            )

    section("Current payment-health signal", "No incident is also a valid result: it means current evidence does not support an active degradation alert.")
    if incidents:
        for inc in incidents:
            severity = str(inc.get("severity") or "low").upper()
            tone = "bad" if severity in {"HIGH", "CRITICAL"} else "warn" if severity == "MEDIUM" else "info"
            st.markdown(
                f"""
<div class="mos-card">
  <div class="mos-card-row">
    <div>
      <div class="mos-card-title">{escape(str(inc.get('scope') or 'Payment route'))}</div>
      <div class="mos-card-sub">{escape(str(inc.get('root_cause') or 'Root cause under investigation'))}</div>
    </div>
    {badge(severity, tone)}
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                kpi("Recent failure rate", percent(inc.get("recent_failure_rate"), 0), "Observed failure rate in the recent window.", "bad" if float(inc.get("recent_failure_rate") or 0) > .5 else "warn")
            with m2:
                kpi("Normal baseline", percent(inc.get("baseline_failure_rate"), 0), "Historical baseline used for comparison.", "neutral")
            with m3:
                kpi("Degradation", percent(inc.get("degradation"), 0), "Increase versus the normal baseline.", "warn")
            with m4:
                kpi("Revenue at risk", money(inc.get("revenue_at_risk"), 0), "Estimated value exposed to this degradation.", "warn")
            evidence = inc.get("evidence", []) or []
            if evidence:
                with st.expander("Why PayGuard raised this incident"):
                    for line in evidence:
                        st.write(f"• {line}")
    else:
        empty_state("No payment-method or bank degradation currently meets PayGuard's evidence threshold.")

    # MERCHANTOS_PAYGUARD_OBSERVABILITY_V1
    #
    # Active incidents are intentionally strict.
    # Even when there is no incident, show the genuine
    # Razorpay Test Mode evidence PayGuard is evaluating.

    terminal_events = [
        e
        for e in events
        if e.get("event_type")
        in {
            "payment.failed",
            "payment.captured",
        }
    ]

    if terminal_events:

        route_df = pd.DataFrame(
            terminal_events
        ).copy()

        if "method" not in route_df.columns:
            route_df["method"] = "unknown"

        if "bank" not in route_df.columns:
            route_df["bank"] = "unknown"

        route_df["method"] = (
            route_df["method"]
            .fillna("unknown")
            .astype(str)
        )

        route_df["bank"] = (
            route_df["bank"]
            .fillna("unknown")
            .astype(str)
        )

        route_df["route"] = (
            route_df["method"]
            + ":"
            + route_df["bank"]
        )

        route_df["timestamp_dt"] = (
            pd.to_datetime(
                route_df["timestamp"],
                utc=True,
                errors="coerce",
            )
        )

        route_df = route_df.dropna(
            subset=["timestamp_dt"]
        )

        if not route_df.empty:

            anchor = (
                route_df[
                    "timestamp_dt"
                ].max()
            )

            recent_start = (
                anchor
                - pd.Timedelta(
                    minutes=60
                )
            )

            recent_df = route_df[
                route_df[
                    "timestamp_dt"
                ] >= recent_start
            ].copy()

            section(
                "Observed route health",
                (
                    "These are the real Razorpay Test Mode "
                    "payment routes PayGuard is monitoring. "
                    "A route can be visible here without "
                    "being unhealthy enough to raise an incident."
                ),
            )

            total_terminal = len(
                route_df
            )

            route_count = int(
                route_df[
                    "route"
                ].nunique()
            )

            recent_terminal = len(
                recent_df
            )

            recent_failures = int(
                (
                    recent_df[
                        "event_type"
                    ]
                    == "payment.failed"
                ).sum()
            )

            recent_rate = (
                recent_failures
                / recent_terminal
                if recent_terminal
                else 0.0
            )

            h1, h2, h3, h4 = st.columns(
                4
            )

            with h1:
                kpi(
                    "Observed payments",
                    str(total_terminal),
                    (
                        "Failed and captured "
                        "Razorpay Test Mode "
                        "payments available "
                        "to PayGuard."
                    ),
                    "info",
                )

            with h2:
                kpi(
                    "Routes monitored",
                    str(route_count),
                    (
                        "Unique payment-method "
                        "and bank combinations."
                    ),
                    "info",
                )

            with h3:
                kpi(
                    "Latest 60 min",
                    str(recent_terminal),
                    (
                        "Payments inside "
                        "PayGuard's current "
                        "incident window."
                    ),
                    "neutral",
                )

            with h4:
                kpi(
                    "Recent failure rate",
                    percent(
                        recent_rate,
                        0,
                    ),
                    (
                        f"{recent_failures} "
                        "failed payment(s) "
                        "inside the latest "
                        "60-minute window."
                    ),
                    (
                        "warn"
                        if recent_failures
                        else "good"
                    ),
                )

            route_rows = []

            for route, group in (
                route_df.groupby(
                    "route",
                    dropna=False,
                )
            ):

                recent_group = group[
                    group[
                        "timestamp_dt"
                    ] >= recent_start
                ]

                total_count = len(
                    group
                )

                failures = int(
                    (
                        group[
                            "event_type"
                        ]
                        == "payment.failed"
                    ).sum()
                )

                captured = int(
                    (
                        group[
                            "event_type"
                        ]
                        == "payment.captured"
                    ).sum()
                )

                recent_count = len(
                    recent_group
                )

                recent_failed = int(
                    (
                        recent_group[
                            "event_type"
                        ]
                        == "payment.failed"
                    ).sum()
                )

                route_recent_rate = (
                    recent_failed
                    / recent_count
                    if recent_count
                    else 0.0
                )

                route_rows.append(
                    {
                        "Payment route":
                            route,

                        "Total":
                            total_count,

                        "Failed":
                            failures,

                        "Captured":
                            captured,

                        "Recent (60m)":
                            recent_count,

                        "Recent failures":
                            recent_failed,

                        "Recent failure rate":
                            route_recent_rate,

                        "Last seen":
                            group[
                                "timestamp_dt"
                            ].max(),
                    }
                )

            health_df = pd.DataFrame(
                route_rows
            )

            health_df = (
                health_df.sort_values(
                    [
                        "Recent failures",
                        "Recent (60m)",
                        "Failed",
                    ],
                    ascending=False,
                )
            )

            display_health = (
                health_df.copy()
            )

            display_health[
                "Recent failure rate"
            ] = (
                display_health[
                    "Recent failure rate"
                ].map(
                    lambda value:
                    percent(
                        value,
                        0,
                    )
                )
            )

            display_health[
                "Last seen"
            ] = (
                display_health[
                    "Last seen"
                ].dt.strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
            )

            st.dataframe(
                display_health,
                hide_index=True,
                use_container_width=True,
                height=280,
            )

            with st.expander(
                "How PayGuard detects a degraded route"
            ):

                st.write(
                    "PayGuard evaluates every "
                    "payment-method and bank route "
                    "separately."
                )

                st.write(
                    "• At least 3 payments must "
                    "exist in the latest "
                    "60-minute window."
                )

                st.write(
                    "• At least 2 of those "
                    "payments must have failed."
                )

                st.write(
                    "• The recent failure rate "
                    "must be at least 50%."
                )

                st.write(
                    "• The failure rate must be "
                    "at least 20 percentage points "
                    "worse than the normal baseline."
                )

                st.write(
                    "If these conditions are not "
                    "met, MerchantOS keeps the route "
                    "visible but correctly does not "
                    "raise an incident."
                )

    else:

        section(
            "Observed route health",
            (
                "Payment-route evidence will "
                "appear here as Razorpay Test Mode "
                "payments are observed."
            ),
        )

        empty_state(
            "No captured or failed Razorpay "
            "Test Mode payments are currently "
            "available for route-health analysis."
        )


    if payguard_history:
        section("Incident history", "Resolved incidents are summarized in plain language; full fields remain available for technical review.")
        for inc in payguard_history[:5]:
            severity = str(inc.get("severity") or "low").title()
            status = str(inc.get("status") or "—").replace("_", " ").title()
            scope = str(inc.get("scope") or "Payment route")
            root = str(inc.get("root_cause") or "Root cause unavailable").replace("_", " ")
            if len(root) > 150:
                root = root[:147] + "…"
            st.markdown(
                f'<div class="mos-card"><div class="mos-card-row"><div><div class="mos-card-title">{escape(scope)}</div><div class="mos-card-sub">{escape(root)}</div></div>{badge(status, "good" if status.lower()=="resolved" else "warn")}</div><div class="mos-card-sub" style="margin-top:.65rem"><strong>{escape(severity)} severity</strong> · Recent failure {escape(percent(inc.get("recent_failure_rate"),0))} vs {escape(percent(inc.get("baseline_failure_rate"),0))} baseline · {escape(money(inc.get("revenue_at_risk"),0))} revenue at risk</div></div>',
                unsafe_allow_html=True,
            )
        with st.expander("Technical incident table"):
            hdf = pd.DataFrame(payguard_history)
            view = pd.DataFrame({
                "Status": hdf.get("status", "—"),
                "Severity": hdf.get("severity", "—").astype(str).str.title(),
                "Scope": hdf.get("scope", "—"),
                "Recent failure": hdf.get("recent_failure_rate", 0).map(lambda x: percent(x, 0)),
                "Baseline": hdf.get("baseline_failure_rate", 0).map(lambda x: percent(x, 0)),
                "Revenue at risk": hdf.get("revenue_at_risk", 0).map(lambda x: money(x, 0)),
                "Root cause": hdf.get("root_cause", "—"),
            })
            st.dataframe(view, hide_index=True, use_container_width=True, height=300)


# -----------------------------
# Digital Twin
# -----------------------------
elif page == "Digital Twin":
    page_header(
        "Simulate",
        "Digital Twin",
        "Before MerchantOS acts, it compares bounded recovery options using expected recovery, cost, risk penalty, and expected net value.",
        [("Simulation only", "info")],
    )

    failed_events = [e for e in events if e.get("event_type") == "payment.failed"]
    if not failed_events:
        empty_state("Digital Twin needs at least one failed Razorpay Test Mode payment.")
    else:
        event_lookup: dict[str, str] = {}
        for e in failed_events:
            label = f"{e.get('payment_id') or compact_id(e.get('event_id'), 12)} · {money(e.get('amount'), 0)} · {str(e.get('method') or 'unknown').title()}"
            event_lookup[label] = e.get("event_id")
        selected = st.selectbox("Failed payment", list(event_lookup.keys()))
        twin = api_get(f"/digital-twin/{event_lookup[selected]}", {}) or {}
        options = twin.get("options", []) or []
        if not twin:
            empty_state("Simulation details are currently unavailable.")
        else:
            risk_detail = twin.get("risk", {}) or {}
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi("Risk score", f"{float(risk_detail.get('risk_score') or 0):.3f}", f"Review begins at {float(risk_detail.get('review_threshold') or review_threshold):.2f}.", risk_tone(risk_detail.get("risk_score"), review_threshold, critical_threshold))
            with c2:
                kpi("Revenue at risk", money(twin.get("revenue_at_risk"), 2), "Estimated value MerchantOS could lose if this failed payment is not recovered.", "warn")
            with c3:
                incident = twin.get("payguard_incident")
                kpi("Payment health", "Degraded" if incident else "No active incident", "PayGuard context changes the value of retrying or switching methods.", "bad" if incident else "good")

            if options:
                ranked = sorted(options, key=lambda x: float(x.get("expected_net_value_inr") or -1e18), reverse=True)
                best = ranked[0]
                section("Recommended intervention", "The option with the strongest expected net value after cost and risk penalties.")
                callout(
                    f"{human_action(best.get('action'))}. Expected net value: {money(best.get('expected_net_value_inr'), 2)}. {best.get('rationale') or ''}",
                    "good" if str(best.get("operational_risk")) == "low" else "warn",
                    "Best simulated option",
                )

                section("Option comparison", "This is simulation, not a guarantee. Only Razorpay Test Mode Payment Links can become provider actions in the current product.")
                max_net = max(max(float(o.get("expected_net_value_inr") or 0), 0) for o in ranked) or 1
                for rank, option in enumerate(ranked, start=1):
                    net = float(option.get("expected_net_value_inr") or 0)
                    width = max(0, min(100, net / max_net * 100))
                    rank_label = "#1 Recommended" if rank == 1 else f"#{rank}"
                    rank_class = "mos-rank best" if rank == 1 else "mos-rank"
                    st.markdown(
                        f"""
<div class="mos-twin-option">
  <div class="mos-card-row">
    <div>
      <div class="mos-card-title"><span class="{rank_class}">{escape(rank_label)}</span>{escape(human_action(option.get('action')))}</div>
      <div class="mos-card-sub">Recovery {percent(option.get('expected_recovery_probability'), 0)} · Cost {money(option.get('expected_cost_inr'), 0)} · Risk penalty {money(option.get('risk_penalty_inr'), 0)}</div>
    </div>
    <div style="text-align:right"><div style="font-weight:740">{escape(money(net, 2))}</div><div style="font-size:.68rem;color:#98a2b3">expected net value</div></div>
  </div>
  <div class="mos-twin-bar"><div style="width:{width:.1f}%"></div></div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                with st.expander("Full simulation table"):
                    odf = pd.DataFrame(ranked)
                    view = pd.DataFrame({
                        "Action": odf.get("action", "—").map(human_action),
                        "Recovery probability": odf.get("expected_recovery_probability", 0).map(lambda x: percent(x, 1)),
                        "Expected recovery": odf.get("expected_recovery_inr", 0).map(lambda x: money(x, 2)),
                        "Expected cost": odf.get("expected_cost_inr", 0).map(lambda x: money(x, 2)),
                        "Risk penalty": odf.get("risk_penalty_inr", 0).map(lambda x: money(x, 2)),
                        "Net value": odf.get("expected_net_value_inr", 0).map(lambda x: money(x, 2)),
                        "Operational risk": odf.get("operational_risk", "—").astype(str).str.title(),
                    })
                    st.dataframe(view, hide_index=True, use_container_width=True)
            else:
                empty_state("No intervention options were generated for this payment.")


# -----------------------------
# Decisions & Actions
# -----------------------------
elif page == "Decisions & Actions":
    page_header(
        "Decide · Act · Verify",
        "Decisions & actions",
        "MerchantOS can recommend many interventions, but provider execution is deliberately restricted to guarded Razorpay Test Mode Payment Links.",
        [("Test actions on" if test_actions_enabled else "Test actions off", "warn" if test_actions_enabled else "neutral")],
    )

    section(
        "Run a decision cycle",
        "Simulation is safe by default. Test Mode execution still requires the environment switch and every guardrail to pass."
    )

    force_redecide = st.checkbox(
        "Re-evaluate existing failed payments",
        value=False,
        help=(
            "Normally leave this off. "
            "Turn it on only when you intentionally "
            "want a fresh decision record for the same payment."
        ),
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        if st.button(
            "Run safe simulation",
            use_container_width=True,
        ):

            try:

                result = api_post(
                    "/orchestrator/run",
                    {
                        "limit": 25,
                        "auto_execute_test_actions":
                            False,
                        "force_redecide":
                            force_redecide,
                    },
                )

                st.session_state[
                    "mos_cycle_feedback"
                ] = {
                    "kind":
                        "simulation",
                    "data":
                        result,
                }

                st.rerun()

            except RuntimeError as exc:
                st.error(str(exc))

    with c2:

        if st.button(
            "Run bounded Test Mode cycle",
            type="primary",
            use_container_width=True,
            disabled=not test_actions_enabled,
        ):

            try:

                result = api_post(
                    "/orchestrator/run",
                    {
                        "limit": 25,
                        "auto_execute_test_actions":
                            True,
                        "force_redecide":
                            force_redecide,
                    },
                )

                st.session_state[
                    "mos_cycle_feedback"
                ] = {
                    "kind":
                        "bounded",
                    "data":
                        result,
                }

                st.rerun()

            except RuntimeError as exc:
                st.error(str(exc))

    with c3:

        if st.button(
            "Verify pending actions",
            use_container_width=True,
        ):

            try:

                result = api_post(
                    "/verify/run",
                    {},
                )

                st.session_state[
                    "mos_cycle_feedback"
                ] = {
                    "kind":
                        "verify",
                    "data":
                        result,
                }

                st.rerun()

            except RuntimeError as exc:
                st.error(str(exc))

    # ---------------------------------------------------------
    # PERSISTENT BUTTON RESULT
    # ---------------------------------------------------------

    feedback = st.session_state.get(
        "mos_cycle_feedback"
    )

    if feedback:

        result = feedback.get("data") or {}
        kind = feedback.get("kind")

        # SAFE SIMULATION
        if kind == "simulation":

            st.success(
                f"Safe simulation complete · "
                f"{result.get('open_failed_candidates', 0)} "
                f"failed payment(s) checked · "
                f"{result.get('new_decisions', 0)} "
                f"new decision(s) · "
                f"{result.get('skipped_existing_decisions', 0)} "
                f"already analyzed · "
                f"no provider action executed."
            )

        # BOUNDED TEST MODE
        elif kind == "bounded":

            started = int(
                result.get(
                    "provider_actions_started",
                    0,
                )
                or 0
            )

            already = int(
                result.get(
                    "provider_actions_already_present",
                    0,
                )
                or 0
            )

            approvals = int(
                result.get(
                    "approval_required",
                    0,
                )
                or 0
            )

            sim_only = int(
                result.get(
                    "simulation_only",
                    0,
                )
                or 0
            )

            blocked_count = int(
                result.get(
                    "blocked",
                    0,
                )
                or 0
            )

            errors = (
                result.get(
                    "execution_errors"
                )
                or []
            )

            if started:

                st.success(
                    f"Bounded Test Mode cycle complete · "
                    f"{started} Razorpay Payment Link "
                    f"action(s) started · "
                    f"{already} already had an action · "
                    f"{approvals} require approval."
                )

            else:

                st.info(
                    f"Bounded cycle complete · "
                    f"no new provider action was needed. "
                    f"Already actioned: {already} · "
                    f"needs approval: {approvals} · "
                    f"simulation only: {sim_only} · "
                    f"blocked: {blocked_count}."
                )

            if errors:

                st.warning(
                    f"{len(errors)} provider "
                    f"execution error(s) occurred."
                )

        # VERIFY
        elif kind == "verify":

            checked = int(
                result.get(
                    "checked",
                    result.get(
                        "verified",
                        0,
                    ),
                )
                or 0
            )

            recovered = int(
                result.get(
                    "recovered",
                    0,
                )
                or 0
            )

            partial = int(
                result.get(
                    "partial",
                    0,
                )
                or 0
            )

            pending = int(
                result.get(
                    "still_pending",
                    0,
                )
                or 0
            )

            failed_count = int(
                result.get(
                    "failed",
                    0,
                )
                or 0
            )

            error_count = int(
                result.get(
                    "errors_count",
                    len(
                        result.get(
                            "errors"
                        )
                        or []
                    ),
                )
                or 0
            )

            if recovered:

                st.success(
                    f"Verification complete · "
                    f"checked {checked} pending action(s) · "
                    f"{recovered} recovered · "
                    f"{partial} partial · "
                    f"{pending} still pending · "
                    f"{failed_count} failed."
                )

            else:

                st.info(
                    f"Verification complete · "
                    f"checked {checked} pending action(s) · "
                    f"{pending} still pending · "
                    f"{partial} partial · "
                    f"{failed_count} failed · "
                    f"no new recovery yet."
                )

            if error_count:

                st.warning(
                    f"{error_count} action(s) "
                    f"could not be verified."
                )
    if not test_actions_enabled:
        st.caption("Bounded execution is disabled in .env. Set MERCHANTOS_TEST_ACTIONS_ENABLED=true only when you intentionally want Razorpay Test Mode Payment Link creation.")

    section("Decision queue", "The operational view shows only the latest decision per payment. Complete history remains in Audit & Safety.")
    latest_decisions = latest_unique(decisions, "event_id")
    if latest_decisions:
        auto_count = sum(d.get("guardrail_status") == "AUTO_ALLOWED_TEST" for d in latest_decisions)
        approval_count = sum(d.get("guardrail_status") == "APPROVAL_REQUIRED" for d in latest_decisions)
        sim_count = sum(d.get("guardrail_status") == "SIMULATION_ONLY" for d in latest_decisions)
        review_count = sum(d.get("guardrail_status") == "BLOCKED" for d in latest_decisions)
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            kpi("Auto-allowed", str(auto_count), "Low-risk Payment Link decisions currently inside the Test Mode autonomy envelope.", "good")
        with q2:
            kpi("Needs approval", str(approval_count), "Payments where a person must approve before a provider action can execute.", "warn")
        with q3:
            kpi("Simulation only", str(sim_count), "Recommendations that remain advisory in the current product.", "info")
        with q4:
            kpi("Risk review", str(review_count), "Payments where recovery automation is suppressed by the risk boundary.", "bad" if review_count else "good")

        ddf = pd.DataFrame(latest_decisions[:8])
        table = pd.DataFrame({
            "Payment": ddf.get("event_id", "—").map(payment_label),
            "Risk": ddf.get("risk_score", 0).map(lambda x: percent(x, 0)),
            "Revenue at risk": ddf.get("revenue_at_risk", 0).map(lambda x: money(x, 0)),
            "Recommended action": ddf.get("recommended_action", "—").map(human_action),
            "Guardrail": ddf.get("guardrail_status", "—").map(human_guardrail),
            "Confidence": ddf.get("confidence", 0).map(lambda x: percent(x, 0)),
        })
        st.dataframe(table, hide_index=True, use_container_width=True, height=330)
        with st.expander("Inspect decision explanations"):
            for item in latest_decisions[:8]:
                decision_card(item, review_threshold)
        with st.expander("View full historical decision table"):
            hdf = pd.DataFrame(decisions)
            history = pd.DataFrame({
                "Created": pd.to_datetime(hdf.get("created_at"), errors="coerce").dt.strftime("%d %b · %H:%M:%S"),
                "Payment": hdf.get("event_id", "—").map(lambda x: compact_id(event_payment_id(x), 13)),
                "Risk": hdf.get("risk_score", 0).map(lambda x: percent(x, 0)),
                "Action": hdf.get("recommended_action", "—").map(human_action),
                "Guardrail": hdf.get("guardrail_status", "—").map(human_guardrail),
            })
            st.dataframe(history, hide_index=True, use_container_width=True, height=360)
    else:
        empty_state("No decisions yet. Run a safe simulation after failed payments are observed.")

    section("Approval inbox", "MerchantOS asks for a human when the amount or risk is outside the auto-action envelope.")
    pending = latest_unique([a for a in approvals if a.get("status") == "PENDING"], "event_id")
    if pending:
        approval_lookup = {f"{payment_label(a.get('event_id'))} · {human_action(a.get('action_type'))}": a for a in pending}
        selected_key = st.selectbox("Pending approval", list(approval_lookup.keys()))
        approval = approval_lookup[selected_key]
        callout(str(approval.get("reason") or "Human approval required before execution."), "warn", "Why approval is required")
        note = st.text_input("Decision note", value="Reviewed in MerchantOS Test Mode")
        a1, a2, _ = st.columns([1, 1, 2])
        with a1:
            if st.button("Approve & execute", type="primary", use_container_width=True):
                try:
                    api_post(f"/approvals/{approval['approval_id']}/decision", {"approved": True, "note": note, "execute_if_approved": True})
                    st.success("Approval recorded. Any permitted Test Mode action was executed through the guarded provider path.")
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))
        with a2:
            if st.button("Reject", use_container_width=True):
                try:
                    api_post(f"/approvals/{approval['approval_id']}/decision", {"approved": False, "note": note, "execute_if_approved": False})
                    st.success("Approval rejected and recorded in the audit trail.")
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))
    else:
        empty_state("No pending approvals. MerchantOS only creates approval requests when policy requires a person in the loop.")

    section("Provider actions & outcomes", "Every executed action is a real Razorpay Test Mode Payment Link with a recorded verification outcome.")
    if actions:
        latest_recovered = next((a for a in sorted(actions, key=lambda x: str(x.get("verified_at") or x.get("created_at") or ""), reverse=True) if a.get("status") == "VERIFIED_RECOVERED"), None)
        if latest_recovered:
            expected_latest = float(latest_recovered.get("expected_recovery") or 0)
            actual_latest = float(latest_recovered.get("actual_recovery") or 0)
            lift_latest = ((actual_latest / expected_latest) - 1) * 100 if expected_latest > 0 else 0
            st.markdown(
                f'<div class="mos-spotlight"><div class="label">Latest verified recovery</div><div class="value">{escape(money(actual_latest,2))}</div><div class="sub">Expected {escape(money(expected_latest,2))} · {lift_latest:+.0f}% vs expected · {escape(payment_label(latest_recovered.get("event_id")))}</div></div>',
                unsafe_allow_html=True,
            )
        adf = pd.DataFrame(actions)
        urls = adf.get("provider_payload", pd.Series([{}] * len(adf))).map(lambda x: (x or {}).get("short_url") if isinstance(x, dict) else None)
        action_view = pd.DataFrame({
            "Created": pd.to_datetime(adf.get("created_at"), errors="coerce").dt.strftime("%d %b · %H:%M"),
            "Action": adf.get("action_id", "—").map(lambda x: compact_id(x, 13)),
            "Status": adf.get("status", "—").astype(str).str.replace("_", " ").str.title(),
            "Expected": adf.get("expected_recovery", 0).map(lambda x: money(x, 2)),
            "Actual": adf.get("actual_recovery", 0).map(lambda x: money(x, 2)),
            "Payment link": urls,
        })
        st.dataframe(
            action_view,
            hide_index=True,
            use_container_width=True,
            column_config={"Payment link": st.column_config.LinkColumn("Payment link", display_text="Open link")},
            height=300,
        )
    else:
        empty_state("No provider actions have been executed yet. MerchantOS can still simulate and decide without creating a payment link.")

    with st.expander("Guardrail policy in plain language"):
        st.markdown(
            f"""
- **Risk below 0.55:** low-risk actions may be eligible for bounded Test Mode execution.
- **Risk 0.55 to below {review_threshold:.2f}:** MerchantOS becomes more conservative; a human may be required.
- **Risk at or above {review_threshold:.2f}:** recovery automation is suppressed and the case is routed to review.
- **Risk at or above {critical_threshold:.2f}:** the case is treated as critical risk.
- **Only Payment Links can execute:** alternate method, retry, and wait remain recommendations/simulations in the current product.
- **RiskNet itself never executes:** execution always passes through the Decision Agent and Guardrails.
"""
        )


# -----------------------------
# Learning & Outcomes
# -----------------------------
elif page == "Learning & Outcomes":
    page_header(
        "Verify · Learn",
        "Learning & outcomes",
        "MerchantOS learns operationally by comparing expected recovery with verified outcomes. The finalized RiskNet model is locked and does not silently retrain itself.",
        [("Outcome tracking active", "good")],
    )

    ratio = float(outcomes.get("realized_vs_expected_ratio") or 0)
    cols = st.columns(4)
    with cols[0]:
        kpi("Recovery performance", f"{ratio:.2f}×" if ratio else "—", "Actual recovery compared with MerchantOS's expected recovery before action.", "good" if ratio >= 1 else "info")
    with cols[1]:
        kpi("Actual recovery", money(outcomes.get("actual_recovery_inr"), 2), "Total provider-verified recovered value.", "good")
    with cols[2]:
        kpi("Expected recovery", money(outcomes.get("expected_recovery_inr"), 2), "Total expected recovery across executed actions.", "purple")
    with cols[3]:
        recovered_count = int(outcomes.get("recovered_actions", sum(a.get("status") == "VERIFIED_RECOVERED" for a in actions)))
        total_count = int(outcomes.get("actions_total", len(actions)))
        kpi("Successful recoveries", f"{recovered_count} / {total_count}", "Verified recoveries compared with executed bounded provider actions.", "info")

    section("What 'Learn' means here", "Outcome learning is explicit and safe. It does not mutate the locked risk model during normal operation.")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi("Risk model", "Locked" if model_locked else "Unlocked", "The finalized risk model cannot silently refit itself during normal operation.", "good" if model_locked else "warn")
    with c2:
        kpi("More training payments", "Not required" if model.get("no_additional_payments_required") else "Check model", "The finalized model uses the existing controlled Test Mode dataset.", "good")
    with c3:
        kpi("Model quality check", "Passed" if model.get("learned_calibrator_quality_gate_passed") else "Safe fallback", "Weak learned models are rejected rather than silently activated.", "good" if model.get("learned_calibrator_quality_gate_passed") else "warn")

    training_readiness = model.get("readiness_at_training", {}) or {}
    training_counts = training_readiness.get("counts", {}) or {}
    section("Locked model training evidence", "These counts come from the finalized RiskNet artifact and remain stable even as new UNLABELED operational payments arrive. Experiment labels are offline training/evaluation metadata only.")
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        kpi("Labeled Test payments", str(training_counts.get("labeled", "—")), "Genuine Razorpay Test Mode observations used at finalization.", "info")
    with t2:
        kpi("Controlled abuse", str(training_counts.get("controlled_abuse", "—")), "Offline controlled-abuse examples in the locked training evidence.", "warn")
    with t3:
        kpi("Benign", str(training_counts.get("benign", "—")), "NORMAL + LEGIT_SHARED_NETWORK examples.", "good")
    with t4:
        kpi("Customers", str(training_counts.get("customers", "—")), "Distinct customers represented when the artifact was finalized.", "purple")

    labels = dataset.get("scenario_labels", {}) or {}
    methods = dataset.get("methods", {}) or {}
    section("Current operational Test Mode dataset", "This is the database currently observed by MerchantOS. Live Payment Journey transactions are intentionally UNLABELED and do not rewrite the locked model's training evidence.")
    d1, d2 = st.columns(2, gap="large")
    with d1:
        if labels:
            label_df = pd.DataFrame([{"Operational label": k.replace("_", " ").title(), "Payments": v} for k, v in labels.items()])
            st.dataframe(label_df, hide_index=True, use_container_width=True)
        else:
            empty_state("No operational payment labels are present yet.")
    with d2:
        if methods:
            method_df = pd.DataFrame([{"Method": k.title(), "Payments": v} for k, v in methods.items()])
            st.dataframe(method_df, hide_index=True, use_container_width=True)
        else:
            empty_state("Payment-method counts are unavailable.")

    if labels and set(labels) == {"UNLABELED"}:
        callout("All current operational payments are UNLABELED. This is expected for Live Payment Journey and does not invalidate the locked RiskNet artifact.", "info", "Operational data policy")

    section("Model validation", "Chronological holdout results from the locked RiskNet calibrator. These metrics are supporting evidence, not the main product story.")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        kpi("Precision", percent(holdout.get("precision"), 1), "Of cases the model flagged in holdout, how many were controlled abuse.", "info")
    with m2:
        kpi("Recall", percent(holdout.get("recall"), 1), "How much controlled abuse the model identified in holdout.", "info")
    with m3:
        kpi("PR-AUC", f"{float(holdout.get('pr_auc') or 0):.4f}", "Ranking quality for the minority abuse class.", "purple")
    with m4:
        kpi("ROC-AUC", f"{float(holdout.get('roc_auc') or 0):.4f}", "Overall ranking separation on chronological holdout.", "purple")

    with st.expander("Technical learning status"):
        st.json(learning)


# -----------------------------
# Audit & Safety
# -----------------------------
elif page == "Audit & Safety":
    page_header(
        "Audit",
        "Audit & safety",
        "Every meaningful decision, approval, action, verification, and model event is recorded in a tamper-evident hash chain.",
        [("Audit verified", "good" if audit_valid else "bad")],
    )

    checked = int(audit_chain.get("checked") or 0)
    cols = st.columns(4)
    with cols[0]:
        kpi("Audit integrity", "Valid" if audit_valid else "Broken", "Hash-chain verification result across stored audit records.", "good" if audit_valid else "bad")
    with cols[1]:
        kpi("Records checked", f"{checked:,}", "Audit records verified from genesis through the current head.", "info")
    with cols[2]:
        kpi("Live Mode", "Blocked", "MerchantOS refuses Live Mode provider operation in this build.", "good")
    with cols[3]:
        kpi("Experiment-label leakage", "Blocked", "Current-event labels are offline-only and do not control operational decisions.", "good")

    section("Safety controls", "MerchantOS makes the allowed action explicit, then shows the boundaries that prevent unsafe shortcuts.")
    safety_controls = [
        ("Provider action surface", "Payment Links only", "The only provider action supported in this product is a guarded Razorpay Test Mode Payment Link.", "info"),
        ("Test actions", "Enabled" if test_actions_enabled else "Disabled", "An explicit environment switch controls whether eligible Test Mode Payment Links may execute.", "warn" if test_actions_enabled else "neutral"),
        ("Razorpay environment", "Test Mode only", "Provider credentials are required to begin with rzp_test_.", "good"),
        ("Risk model execution", "Not allowed", "RiskNet contributes evidence; Decision Agent + Guardrails own the action boundary.", "good"),
        ("Manual fake payment ingestion", "Disabled", "Payment observations come from signed webhooks, provider sync, or the Test Checkout flow.", "good"),
        ("Synthetic active model inputs", "Forbidden", "Synthetic stress artifacts are not active inputs to RiskNet.", "good"),
        ("Current experiment label", "Offline only", "Labels can train/evaluate the model but cannot choose a live operational action.", "good"),
        ("Automatic model refit", "Disabled", "The finalized RiskNet artifact is locked by default.", "good"),
    ]
    grid = st.columns(2)
    for idx, (name, state, desc, tone) in enumerate(safety_controls):
        with grid[idx % 2]:
            st.markdown(
                f"""
<div class="mos-card">
  <div class="mos-card-row"><div class="mos-card-title">{escape(name)}</div>{badge(state, tone)}</div>
  <div class="mos-card-sub">{escape(desc)}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    section("Recent audit activity", "A readable slice of the tamper-evident event stream.")
    audit_events = audit.get("events", []) or []
    if audit_events:
        adf = pd.DataFrame(audit_events)
        view = pd.DataFrame({
            "#": adf.get("seq", "—"),
            "Time": pd.to_datetime(adf.get("created_at"), errors="coerce").dt.strftime("%d %b · %H:%M:%S"),
            "Type": adf.get("event_type", "—").astype(str).str.replace(".", " → ", regex=False),
            "Entity": adf.get("entity_type", "—").astype(str).str.title(),
            "Entity ID": adf.get("entity_id", "—").map(lambda x: compact_id(x, 14)),
        })
        st.dataframe(view, hide_index=True, use_container_width=True, height=430)
    else:
        empty_state("No audit events are recorded yet.")

    with st.expander("Technical audit evidence"):
        if audit_chain.get("head_hash"):
            st.caption("Current hash-chain head")
            st.markdown(f'<div class="mos-hash">{escape(str(audit_chain.get("head_hash")))}</div>', unsafe_allow_html=True)
        st.caption("Raw verification response")
        st.json(audit_chain)



# MERCHANTOS_VISIBILITY_FIX_V1
st.markdown("""
<style>

/* Checkbox text */
div[data-testid="stCheckbox"] label p,
div[data-testid="stCheckbox"] label span {
    color: #334155 !important;
    -webkit-text-fill-color: #334155 !important;
    opacity: 1 !important;
}

/* Success / warning / info message text */
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span,
div[data-testid="stAlert"] div {
    color: #1e293b !important;
    -webkit-text-fill-color: #1e293b !important;
    opacity: 1 !important;
}

/* Make message text easy to read */
div[data-testid="stAlert"] p {
    font-weight: 600 !important;
}

</style>
""", unsafe_allow_html=True)
