from __future__ import annotations

import hashlib
import os


def stable_hash(value: str | None, namespace: str) -> str:
    """Hash test-context identifiers before they enter the Risk Graph.

    The graph needs stable joins, not raw browser/IP/customer values. In Test Mode
    this is primarily hygiene, but using the same pattern now prevents us from
    designing around raw sensitive identifiers later.
    """
    if not value:
        return "unknown"
    salt = os.getenv("MERCHANTOS_HASH_SALT", "merchantos-test-mode-only")
    digest = hashlib.sha256(f"{salt}|{namespace}|{value}".encode()).hexdigest()[:20]
    return f"{namespace}_{digest}"
