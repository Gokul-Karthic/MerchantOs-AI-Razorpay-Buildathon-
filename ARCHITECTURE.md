# MerchantOS AI v1.4.1 Architecture

```mermaid
flowchart LR
    U[Merchant / Test Customer] --> D[Streamlit Dashboard]
    D --> A[FastAPI MerchantOS API]
    A --> R[Razorpay Test Mode]
    R --> W[Signed Webhooks]
    W --> A

    A --> O[OBSERVE\nPayment + webhook ingestion]
    O --> RN[UNDERSTAND\nRiskNet Hybrid v2]
    O --> PG[UNDERSTAND\nPayGuard]
    RN --> DT[SIMULATE\nDigital Twin]
    PG --> DT
    DT --> DA[DECIDE\nDecision Agent]
    DA --> G[GUARD\nDeterministic Guardrails]
    G -->|Auto-allowed Test Mode| PL[ACT\nRazorpay Payment Link]
    G -->|Approval| H[Human Approval]
    G -->|High risk| B[Review / Block]
    PL --> V[VERIFY\nWebhook + Provider API]
    V --> L[LEARN\nExpected vs Actual]

    O -.-> AU[(Tamper-evident Audit)]
    RN -.-> AU
    PG -.-> AU
    DT -.-> AU
    DA -.-> AU
    G -.-> AU
    PL -.-> AU
    V -.-> AU
    L -.-> AU

    A --> DB[(SQLite Test Mode state)]
    RN --> M[(Locked RiskNet artifact)]
```

## Runtime boundaries

- **Razorpay** remains the payment provider. MerchantOS does not replace the gateway.
- **FastAPI** owns provider integration, model scoring, decisions, guardrails, actions, verification, and persistence.
- **Streamlit** is a presentation/client layer and never accesses SQLite directly.
- **RiskNet** provides evidence only. It cannot call Razorpay actions.
- **Guardrails** are deterministic and own the provider-action boundary.
- **Docker Compose** places API and dashboard on an internal network while exposing only ports 8000 and 8501 to the host.
