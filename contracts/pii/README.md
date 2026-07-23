# SP-60: portable PII policy and receipt contract (v1)

**Status:** development / conformance only. This bundle does not publish a live policy, provision a
signing key, issue a permit, or activate any runtime gate. See
[ADR-0018](../../docs/decisions/0018-pii-wall-purpose-bound-data-boundary.md) D11 and
[SPEC-PII-POLICY](../../docs/specs/SPEC-PII-POLICY-platform-policy-contract.md) "Development exit".

Implements `task-sp-60-pii-policy-contract-v1`
(`docs/specs/task-sp-60-pii-policy-contract-v1.md`), scoped to `contracts/pii/**` and `tests/**` only.

## Layout

```text
contracts/pii/
  schemas/v1/            versioned JSON Schemas for every SPEC-PII-POLICY interface
  fixtures/v1/positive/  fixtures that must validate (and, where applicable, resolve an
                         allowed profile downgrade correctly)
  fixtures/v1/negative/  fixtures that must fail: downgrade-violation, replay, raw-receipt,
                         lifecycle-collapse, skew (one or more fixtures per category)
  validator/             dependency-free Python: structural (schema_check.py) + semantic
                         (pii_contract_validator.py) rules
  tooling/build_manifest.py   regenerates the content-addressed manifest
  manifest/pii-contract-manifest.v1.json   canonical digest over schemas/v1 + fixtures/v1
```

## Why a hand-rolled JSON Schema validator

This repository declares no third-party Python dependency (no `requirements.txt` /
`pyproject.toml`), and the task's execution profile is `offline-contract`. Relying on an ambient,
undeclared `jsonschema` install would make the contract non-portable, so `validator/schema_check.py`
implements only the JSON Schema subset (`type`, `required`, `properties`, `additionalProperties`,
`enum`, `const`, `pattern`, `minLength`, `minItems`, `items`, same-directory `$ref`) this contract
actually needs.

## Running the probes

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_pii_contract_schema_and_fixtures.py` is probe **pii-contract-schema-and-fixtures**
  (AC-SP60-1): every positive fixture validates; every negative fixture -- covering all five
  required categories -- is rejected.
- `tests/test_pii_contract_manifest.py` is probe **pii-contract-manifest** (AC-SP60-2): the manifest
  digest is independently recomputed and compared, and an absence scan confirms no active policy,
  signing key, permit issuer, network call, or server entrypoint exists anywhere in the bundle.

Regenerate the manifest after editing any schema or fixture:

```bash
python3 contracts/pii/tooling/build_manifest.py
python3 contracts/pii/tooling/build_manifest.py --check   # verify without writing
```

## Non-activation boundary

- No credential, cloud key, active policy, provider call, runtime gate, deletion, or export.
- Every `integrity`/`signer` value in every fixture is a `dev-fixture-*` placeholder, never a real key.
- The canonical `PIIPolicyBundle` fixture carries `publication_status: "unpublished_development_fixture"`.
- `contracts/pii/validator/` exposes only `validate_*`, `check_*`, `scan_*`, `aggregate_*`,
  `resolve_*`, and `evaluate_*` callables -- no `issue_*`, `publish_*`, `activate_*`, `grant_*`, or
  `provision_*` function exists (enforced by `AbsenceScanTests` in
  `tests/test_pii_contract_manifest.py`).
- Publishing a live policy, provisioning trust keys, and component activation remain separate,
  human-approved owner transitions (ADR-0018 D11; SPEC-PII-POLICY REQ-PII-POL-10).
