"""Portable, non-activating PII policy/receipt contract validator (SP-60 / SPEC-PII-POLICY).

This package contains pure, offline functions only. Nothing here issues a permit,
publishes a policy, provisions a signing key, or calls a network endpoint. See
``contracts/pii/README.md`` for the non-activation boundary this package must respect.
"""

from __future__ import annotations
