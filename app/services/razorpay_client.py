from __future__ import annotations

import os
from typing import Any

import requests


class RazorpayClient:
    """Razorpay adapter hard-locked to Test Mode keys."""

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self) -> None:
        self.key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()

    @property
    def has_credentials(self) -> bool:
        return bool(self.key_id and self.key_secret)

    @property
    def is_test_mode(self) -> bool:
        return self.key_id.startswith("rzp_test_")

    @property
    def configured(self) -> bool:
        return self.has_credentials and self.is_test_mode

    def _require_test_mode(self) -> None:
        if not self.has_credentials:
            raise RuntimeError("Razorpay Test Mode credentials are not configured.")
        if not self.is_test_mode:
            raise RuntimeError("MerchantOS refuses non-Test Razorpay keys. Use an rzp_test_ key.")

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        self._require_test_mode()
        response = requests.request(
            method,
            f"{self.BASE_URL}{path}",
            auth=(self.key_id, self.key_secret),
            timeout=20,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def create_order(
        self,
        amount_inr: float,
        receipt: str,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": int(round(amount_inr * 100)),
            "currency": "INR",
            "receipt": receipt,
        }
        if notes:
            payload["notes"] = notes
        return self._request("POST", "/orders", json=payload)

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/orders/{order_id}")

    def fetch_orders(self, count: int = 100, skip: int = 0) -> dict[str, Any]:
        return self._request("GET", "/orders", params={"count": count, "skip": skip})

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return self._request("GET", f"/payments/{payment_id}")

    def fetch_payments(self, count: int = 100, skip: int = 0) -> dict[str, Any]:
        return self._request(
            "GET",
            "/payments",
            params={"count": count, "skip": skip, "expand[]": "card"},
        )

    def fetch_order_payments(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/orders/{order_id}/payments")

    def create_payment_link(
        self,
        *,
        amount_inr: float,
        reference_id: str,
        description: str,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": int(round(amount_inr * 100)),
            "currency": "INR",
            "accept_partial": False,
            "reference_id": reference_id[:40],
            "description": description[:2048],
            "reminder_enable": False,
        }
        if notes:
            payload["notes"] = {str(k)[:256]: str(v)[:256] for k, v in list(notes.items())[:15]}
        return self._request("POST", "/payment_links", json=payload)

    def fetch_payment_link(self, payment_link_id: str) -> dict[str, Any]:
        return self._request("GET", f"/payment_links/{payment_link_id}")

    def cancel_payment_link(self, payment_link_id: str) -> dict[str, Any]:
        return self._request("POST", f"/payment_links/{payment_link_id}/cancel")
