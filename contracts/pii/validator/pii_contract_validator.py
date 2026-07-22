"""Deterministic semantic validator for SPEC-PII-POLICY / ADR-0018 (SP-60).

Pure, offline functions only: every function here takes JSON-shaped Python data
in, returns error strings out, and performs no I/O beyond reading the bundled
schema files. None of it issues a permit, publishes a policy, mints a signing
key, or contacts a network endpoint -- see ``contracts/pii/README.md``.

Public surface is intentionally verb-limited to ``validate_*``, ``check_*``,
``scan_*``, ``aggregate_*``, ``resolve_*``, and ``evaluate_*`` -- the absence
scan in ``tests/test_pii_contract_manifest.py`` asserts no ``issue_*``,
``publish_*``, ``activate_*``, or ``grant_*`` callable exists in this module.
"""

from __future__ import annotations

import re
from typing import Any

from . import schema_check

# ---------------------------------------------------------------------------
# REQ-PII-POL-2 / REQ-PII-POL-3 closed taxonomy (single source of truth is the
# schema files; these orderings encode semantics a plain enum cannot express).
# ---------------------------------------------------------------------------

PROFILE_ORDER: dict[str, int] = {"PW0": 0, "PW1": 1, "PW2": 2}
"""Strictness order: lower index == stricter/less-admitting profile."""

TERMINAL_COMPLETE_DISPOSITIONS = frozenset({"complete", "excluded"})
"""Per-store dispositions that do not block an aggregate 'complete' claim."""

BLOCKING_DISPOSITION_SEVERITY: tuple[str, ...] = (
    "unavailable",
    "failed",
    "backup_pending",
    "immutable_retention",
    "pending",
)
"""Most-severe-first order used to pick the honest aggregate disposition when
coverage is not complete. The aggregate stays inside the same closed
REQ-PII-POL-7 enum -- it is never a synthetic 'partial' value -- so a claimed
'complete'/'deleted'/'clean' can be checked against a real, comparable value."""

_RAW_LEAK_KEY_PATTERN = re.compile(
    r"(^|_)(raw|raw_value|plaintext|reversible_token|prompt_excerpt|"
    r"provider_payload|stable_fingerprint|prompt|payload)($|_)",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


# ---------------------------------------------------------------------------
# Structural (schema) validation
# ---------------------------------------------------------------------------


def validate_against_schema(instance: Any, schema_name: str) -> list[str]:
    """Validate ``instance`` against a named schema in ``schemas/v1``."""
    schema = schema_check.load_schema(schema_name)
    return schema_check.validate(instance, schema)


# ---------------------------------------------------------------------------
# REQ-PII-POL-3: cumulative profiles, consumer may only go stricter
# ---------------------------------------------------------------------------


def resolve_effective_profile(policy_profile: str, requested_profile: str) -> str:
    """Return the effective profile for a consumer request.

    A consumer may enforce a *stricter* profile than the owner-selected policy
    profile (ADR-0018 D3 / REQ-PII-POL-3), but never a looser one. Raises
    ``ValueError`` if ``requested_profile`` would downgrade below the policy
    minimum -- callers in the test suite convert this into a fixture failure.
    """
    if policy_profile not in PROFILE_ORDER or requested_profile not in PROFILE_ORDER:
        raise ValueError(f"unknown profile in ({policy_profile!r}, {requested_profile!r})")
    if PROFILE_ORDER[requested_profile] > PROFILE_ORDER[policy_profile]:
        raise ValueError(
            f"requested profile {requested_profile!r} is less strict than "
            f"policy-selected profile {policy_profile!r}; downgrade rejected"
        )
    return requested_profile


# ---------------------------------------------------------------------------
# REQ-PII-POL-4 / P-PII-POL-2: envelope propagation must never widen
# ---------------------------------------------------------------------------


def check_no_widening(parent: dict[str, Any], child: dict[str, Any]) -> list[str]:
    """Verify a derived (child) DataEnvelope never widens beyond its parent.

    Covers field widening, sink widening, and expiry extension from
    SPEC-PII-POLICY P-PII-POL-2.
    """
    errors: list[str] = []

    parent_fields = set(parent.get("allowed_fields", []))
    child_fields = set(child.get("allowed_fields", []))
    if not child_fields.issubset(parent_fields):
        errors.append(
            f"field widening: child allowed_fields {sorted(child_fields - parent_fields)} "
            "not present in parent allowed_fields"
        )

    parent_sinks = set(parent.get("allowed_sinks", []))
    child_sinks = set(child.get("allowed_sinks", []))
    if not child_sinks.issubset(parent_sinks):
        errors.append(
            f"sink widening: child allowed_sinks {sorted(child_sinks - parent_sinks)} "
            "not present in parent allowed_sinks"
        )

    parent_expiry = parent.get("expires_at")
    child_expiry = child.get("expires_at")
    if parent_expiry and child_expiry and child_expiry > parent_expiry:
        errors.append(
            f"expiry extension: child expires_at {child_expiry!r} is later than "
            f"parent expires_at {parent_expiry!r}"
        )

    if parent.get("policy_revision") != child.get("policy_revision"):
        errors.append(
            "policy revision mismatch: child envelope must carry the same "
            "policy_revision as its parent unless re-evaluated under a new bundle"
        )

    if parent.get("tenant_id") != child.get("tenant_id"):
        errors.append("tenant widening: child envelope tenant_id differs from parent tenant_id")

    return errors


# ---------------------------------------------------------------------------
# REQ-PII-POL-5 / P-PII-POL-2: permit issuance must never widen its envelope
# ---------------------------------------------------------------------------


def check_permit_widen(envelope: dict[str, Any], permit: dict[str, Any]) -> list[str]:
    """Verify a PIIPermit stays within the DataEnvelope it is minted against."""
    errors: list[str] = []

    envelope_fields = set(envelope.get("allowed_fields", []))
    permit_fields = set(permit.get("allowed_fields", []))
    if not permit_fields.issubset(envelope_fields):
        errors.append(
            f"field widening: permit allowed_fields {sorted(permit_fields - envelope_fields)} "
            "exceed the source envelope's allowed_fields"
        )

    envelope_sinks = set(envelope.get("allowed_sinks", []))
    permit_sinks = set(permit.get("allowed_sinks", []))
    if not permit_sinks.issubset(envelope_sinks):
        errors.append(
            f"sink widening: permit allowed_sinks {sorted(permit_sinks - envelope_sinks)} "
            "exceed the source envelope's allowed_sinks"
        )

    envelope_expiry = envelope.get("expires_at")
    permit_expiry = permit.get("expires_at")
    if envelope_expiry and permit_expiry and permit_expiry > envelope_expiry:
        errors.append("expiry extension: permit expires_at is later than its source envelope expires_at")

    if envelope.get("tenant_id") != permit.get("tenant_id"):
        errors.append("tenant mismatch: permit tenant_id differs from source envelope tenant_id")

    envelope_purpose = envelope.get("purpose_id")
    if envelope_purpose and envelope_purpose != permit.get("purpose_id"):
        errors.append("purpose mismatch: permit purpose_id differs from source envelope purpose_id")

    return errors


# ---------------------------------------------------------------------------
# REQ-PII-POL-5 / P-PII-POL-2: single-purpose, never reused for another sink
# ---------------------------------------------------------------------------


def check_permit_replay(permit: dict[str, Any], usage_records: list[dict[str, Any]]) -> list[str]:
    """Detect a permit being reused outside its granted scope, or reused at all
    once its single-use nonce has already been consumed.
    """
    errors: list[str] = []
    allowed_sinks = set(permit.get("allowed_sinks", []))
    tenant_id = permit.get("tenant_id")
    purpose_id = permit.get("purpose_id")

    seen_nonce_uses = 0
    for index, usage in enumerate(usage_records):
        if usage.get("nonce") == permit.get("nonce"):
            seen_nonce_uses += 1
            if seen_nonce_uses > 1:
                errors.append(f"replay: nonce {permit.get('nonce')!r} reused at usage[{index}]")
        if usage.get("sink") not in allowed_sinks:
            errors.append(f"replay: usage[{index}] sink {usage.get('sink')!r} is outside permit.allowed_sinks")
        if usage.get("tenant_id") != tenant_id:
            errors.append(f"replay: usage[{index}] tenant_id {usage.get('tenant_id')!r} != permit tenant_id {tenant_id!r}")
        if usage.get("purpose_id") != purpose_id:
            errors.append(f"replay: usage[{index}] purpose_id {usage.get('purpose_id')!r} != permit purpose_id {purpose_id!r}")

    return errors


# ---------------------------------------------------------------------------
# REQ-PII-POL-6 / P-PII-POL-3: receipts never carry raw, reversible, or
# provider-payload data
# ---------------------------------------------------------------------------


def scan_receipt_for_raw_leakage(receipt: dict[str, Any]) -> list[str]:
    """Scan a receipt-shaped object for forbidden raw/reversible/identifying content.

    This is defense in depth over the structural schema: a schema cannot prove
    the *absence* of an unnamed field, so this walks the whole document.
    """
    errors: list[str] = []

    for key, value in _walk(receipt):
        if _RAW_LEAK_KEY_PATTERN.search(key):
            errors.append(f"raw leakage: forbidden field name '{key}' present in receipt")
        if isinstance(value, str):
            if _EMAIL_PATTERN.search(value):
                errors.append(f"raw leakage: field '{key}' contains an email-shaped value")
            if _SSN_PATTERN.search(value):
                errors.append(f"raw leakage: field '{key}' contains an SSN-shaped value")

    for digest_field in ("input_digest", "output_digest"):
        value = receipt.get(digest_field)
        if value is not None and not _DIGEST_PATTERN.match(str(value)):
            errors.append(
                f"raw leakage: '{digest_field}' value {value!r} is not a well-formed "
                "sha256 digest -- a non-digest value here would expose raw/derived content"
            )

    return errors


def _walk(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a JSON-shaped structure into (dotted_key, leaf_value) pairs."""
    out: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            out.append((path, value))
            out.extend(_walk(value, path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            path = f"{prefix}[{index}]"
            out.extend(_walk(value, path))
    return out


# ---------------------------------------------------------------------------
# REQ-PII-POL-7 / P-PII-POL-4: lifecycle aggregation cannot collapse partial
# coverage into 'complete'
# ---------------------------------------------------------------------------


def aggregate_lifecycle(store_states: list[dict[str, Any]]) -> str:
    """Compute the honest aggregate disposition for a set of per-store states.

    Returns ``"complete"`` only when every store is 'complete' or deliberately
    'excluded' with at least one 'complete'. Otherwise returns the most severe
    blocking disposition present (SPEC-PII-POLICY REQ-PII-POL-7: the seven
    per-store states "remain distinct; aggregation cannot turn partial
    coverage into 'deleted' or 'clean'" -- so the aggregate stays inside that
    same closed enum rather than a synthetic value outside it). An empty
    ``store_states`` has no evidence and aggregates to 'unavailable'.
    """
    if not store_states:
        return "unavailable"
    dispositions = [state.get("disposition") for state in store_states]
    if all(d in TERMINAL_COMPLETE_DISPOSITIONS for d in dispositions) and "complete" in dispositions:
        return "complete"
    for candidate in BLOCKING_DISPOSITION_SEVERITY:
        if candidate in dispositions:
            return candidate
    # Every store was 'excluded' with none 'complete' and none blocking: there
    # is no positive evidence of completion, so treat as unavailable.
    return "unavailable"


def check_lifecycle_aggregation(deletion_receipt: dict[str, Any]) -> list[str]:
    """Verify a DeletionReceipt's claimed top-level disposition matches its
    itemized store_states -- the collapse P-PII-POL-4 forbids.
    """
    store_states = deletion_receipt.get("store_states", [])
    claimed = deletion_receipt.get("disposition")
    honest = aggregate_lifecycle(store_states)

    errors: list[str] = []
    if claimed in ("deleted", "clean"):
        errors.append(
            f"lifecycle collapse: disposition claims non-conformant literal {claimed!r}; "
            "only the closed REQ-PII-POL-7 disposition values are permitted"
        )
    elif honest != claimed:
        errors.append(
            f"lifecycle collapse: disposition claims {claimed!r} but store_states "
            f"{store_states!r} only support {honest!r}"
        )
    return errors


# ---------------------------------------------------------------------------
# REQ-PII-POL-8 / P-PII-POL-5: skew, outage, revocation block new processing
# without erasing history
# ---------------------------------------------------------------------------


def check_policy_skew(consumer_pin: dict[str, Any], bundle: dict[str, Any], *, reference_now: str) -> list[str]:
    """Verify a consumer's pinned schema major / policy revision / signer trust
    profile is still compatible with the current PIIPolicyBundle.

    Returns a non-empty error list (blocking new processing) on schema-major
    mismatch, stale/mismatched policy revision, signer trust mismatch, or a
    bundle that is expired/not-yet-valid relative to ``reference_now``. This
    function performs no mutation, so historical provenance already recorded
    elsewhere is untouched by a skew finding (ADR-0018 D8/REQ-PII-POL-8).
    """
    errors: list[str] = []

    compat = bundle.get("compatibility", {})
    schema_major = consumer_pin.get("schema_major")
    min_major = compat.get("min_supported_major")
    max_major = compat.get("max_supported_major")
    if schema_major is None or min_major is None or max_major is None or not (min_major <= schema_major <= max_major):
        errors.append(
            f"skew: consumer schema_major {schema_major!r} outside bundle-supported "
            f"range [{min_major!r}, {max_major!r}]"
        )

    if consumer_pin.get("policy_revision_pin") != bundle.get("policy_revision"):
        errors.append(
            f"skew: consumer policy_revision_pin {consumer_pin.get('policy_revision_pin')!r} "
            f"!= current bundle policy_revision {bundle.get('policy_revision')!r}"
        )

    signer = bundle.get("signer", {})
    if consumer_pin.get("signer_trust_profile") != signer.get("key_id"):
        errors.append(
            f"skew: consumer signer_trust_profile {consumer_pin.get('signer_trust_profile')!r} "
            f"!= bundle signer key_id {signer.get('key_id')!r}"
        )

    issued_at = bundle.get("issued_at", "")
    expires_at = bundle.get("expires_at", "")
    if issued_at and reference_now < issued_at:
        errors.append(f"skew: bundle not yet valid (issued_at {issued_at!r} is after reference_now {reference_now!r})")
    if expires_at and reference_now > expires_at:
        errors.append(f"skew: bundle expired (expires_at {expires_at!r} is before reference_now {reference_now!r})")

    return errors


# ---------------------------------------------------------------------------
# Fixture-case dispatch used by the test suite
# ---------------------------------------------------------------------------


def evaluate_case(case: dict[str, Any]) -> list[str]:
    """Evaluate one fixture case object and return its validation errors.

    An empty list means the case is admissible (expected for every fixture
    under ``fixtures/v1/positive``); a non-empty list means the case was
    correctly rejected (expected for every fixture under
    ``fixtures/v1/negative``).
    """
    category = case.get("category")

    if category == "schema":
        return validate_against_schema(case["instance"], case["schema"])

    if category == "profile-downgrade-allowed":
        try:
            resolve_effective_profile(case["policyMinimumProfile"], case["consumerRequestedProfile"])
        except ValueError as exc:
            return [str(exc)]
        return []

    if category == "permit-issuance-allowed":
        errors = validate_against_schema(case["envelope"], "data-envelope.schema.json")
        errors += validate_against_schema(case["permit"], "pii-permit.schema.json")
        errors += check_permit_widen(case["envelope"], case["permit"])
        return errors

    if category == "downgrade-violation":
        mode = case.get("mode")
        if mode == "envelope-propagation":
            return check_no_widening(case["parentEnvelope"], case["childEnvelope"])
        if mode == "permit-issuance":
            return check_permit_widen(case["envelope"], case["permit"])
        if mode == "profile-downgrade":
            try:
                resolve_effective_profile(case["policyMinimumProfile"], case["consumerRequestedProfile"])
            except ValueError as exc:
                return [str(exc)]
            return []
        raise ValueError(f"unknown downgrade-violation mode: {mode!r}")

    if category == "lifecycle-aggregation-honest":
        errors = validate_against_schema(case["deletionReceipt"], "deletion-receipt.schema.json")
        errors += check_lifecycle_aggregation(case["deletionReceipt"])
        return errors

    if category == "replay":
        return check_permit_replay(case["permit"], case["usageRecords"])

    if category == "raw-receipt":
        return scan_receipt_for_raw_leakage(case["receipt"])

    if category == "lifecycle-collapse":
        return check_lifecycle_aggregation(case["deletionReceipt"])

    if category == "skew":
        return check_policy_skew(case["consumerPin"], case["bundle"], reference_now=case["referenceNow"])

    raise ValueError(f"unknown fixture category: {category!r}")
