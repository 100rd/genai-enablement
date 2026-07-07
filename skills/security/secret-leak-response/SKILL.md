---
name: secret-leak-response
description: Use when the change-gate BLOCKs on a `secret_in_change` verifier or a `secret_in_state` Sentinel finding fires — a credential/key has entered a diff or is live in cluster state. Staged containment (confirm, scope, rotate, revoke, verify, learn) with per-step autonomy tiers. NOT for CVE-in-SBOM or IAM-drift findings.
version: 0.1.0
tags: [security, runbook, secrets, incident-response]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T3
license: MIT
# runbook extension namespace:
category: secret-exposure
severity: critical
trigger: secret_in_change gate BLOCK / secret_in_state Sentinel finding (per ADR-0008)
---

# Secret Leak Response

Runbook-type skill. Each step is tagged with the autonomy tier required to execute it
(platform glossary: T1 read-only auto · T2 advisory — recommend, a human acts · T3 requires
explicit human approval within a window). An agent operating below a step's tier stops and
escalates with its findings.

Seeded from ADR-0008 build order S3 — the `security/` response runbook for
the secret verifier/detector family (`secret_in_change` gate BLOCK primary, `secret_in_state`
Sentinel defense-in-depth). **ADR-0008 is accepted on `main`; the gate verifier and the detector
are not yet built; those capabilities below are design-stage.** Maps to the SIRL loop
(per ADR-0008 program): DETECTED → TRIAGED (Steps 1–2) → CONTAINED
(Steps 3–4) → RECOVERED (Step 5) → LEARNED (Step 6); the durable ERADICATED fix runs through
the factory (Step 6 / D9).

## Trigger

- `secret_in_change` gate verifier returns **BLOCK** — a secret was added in a diff.
- `secret_in_state` Sentinel detector finding — a secret is live in ConfigMap/env/state that
  bypassed the gate (defense-in-depth).

## Steps

### Step 1 — Confirm the finding from its fingerprint and location [T1, auto]

Per ADR-0008 D3, a secret-bearing finding carries **only a fingerprint and a
location** (repo / path / line, or ConfigMap / key) — the secret value is redacted before the
finding is persisted, before it enters the audit trail, and before any reasoner prompt.
**Never read, echo, print, log, reconstruct, or commit the secret value** at any step of this
runbook. Work from location metadata only.

```bash
# Inspect location metadata only — do NOT cat/print the secret value
echo "finding=${fingerprint}  location=${repo}:${path}:${line}"
# secret_in_state: identify the object and key, never its data
kubectl get <kind> <name> -n <ns> -o jsonpath='{.metadata.name}{" "}{.metadata.namespace}'
```

If the location resolves to a non-secret (test fixture, documented example), record a false
positive and close.

### Step 2 — Scope the exposure [T1, auto]

Deterministic inputs to classify blast radius — gather all three, do not guess:

```bash
# (a) is the source repository public? public exposure escalates severity to critical
gh repo view <owner/repo> --json visibility -q .visibility
# (b) history reach — how many commits carry the fingerprinted path (path only, never the value)
git log --oneline -- <path> | wc -l
# (c) consumers — which workloads read this secret name (mounts / envFrom / secretKeyRef)
kubectl get pods -A -o json | jq -r '.items[] | select(.. | .name? == "<secret-name>") | .metadata.namespace + "/" + .metadata.name'
```

Classify from the inputs: **public repo → critical**; private + long history → high; internal
+ single consumer → medium. **Preserve this evidence before any containment** (ADR-0008 D7:
forensic evidence first).

### Step 3 — Rotate the credential at the source [T3, requires human approval]

State-changing, security-sensitive, reversible-with-effort → **T3 (HITL within a window)** per
the security action-tier table (ADR-0008 D6). **Rotate — never delete the key**
(deletion is NEVER-T4). Use the platform secret manager; see the
[`security/secrets-vault-manager`](../secrets-vault-manager/SKILL.md) skill for the how
(rotation workflows, dynamic secrets, dual-account / overlap-window strategies).

```bash
# Perform via the secret manager (see secrets-vault-manager) — generate a NEW version/credential.
# e.g. vault kv put … | aws secretsmanager rotate-secret … | az keyvault secret set …
# The manager owns the mechanism; this step only authorizes and drives it.
```

### Step 4 — Revoke/invalidate the leaked credential [T3, requires human approval]

Separate approval from Step 3 — **do not bundle.** Once consumers are on the new credential,
invalidate the **old** one at the provider (revoke the token / deactivate the old key version).
Still **rotate/revoke, never delete the key**, and **never disable audit logging or any security
control** (both NEVER-T4).

### Step 5 — Verify consumers healthy post-rotation [T1, auto]

```bash
kubectl rollout status deployment/<consumer> -n <ns>
# confirm consumers authenticate with the new credential AND the old credential is now rejected
```

The old credential must return auth failure (401/403); a still-live old credential means the
revoke in Step 4 did not take — return to Step 4, do not close.

### Step 6 — Record the lesson (LEARNED) [T1, auto]

LEARNED stage of the SIRL loop. Draft a forensics-aware post-incident note (machine drafts,
**human finalizes** — ADR-0008 D8). Record fingerprint + location + root cause
(**never the value**). Propose the durable fix as a **factory task** (ADR-0008 D9): a
committed spec with `task_id`, class, and tier; the P0 lane buys queue position,
**never a gate skip**. The containment counts `verified` only from independent confirmation
(never self-report).

## Hard constraints (NEVER-T4 — non-amendable by agents; ADR-0008 D6)

- **Rotate/revoke the credential — never *delete* a credential or key.** Deletion is NEVER-T4.
- **Never disable or modify audit logging** — this entire response must remain fully audited.
- **Never touch the platform-design security substrate** (Cedar / OPA / Kyverno / KMS) — it is
  owned by platform-design; this domain consumes, never authors it.
- **Never mutate the skills-registry trust store** (`skills-lock.json` / CODEOWNERS / this
  runbook's success criteria).
- **The secret value never leaves as a value** — no echo/print/log/commit of the secret, ever
  (ADR-0008 D3).

## Escalation

If rotation cannot complete (a consumer will not cut over, provider rotation fails), or the
exposure is public and long-lived, escalate to **SecOps on-call** with the preserved evidence
bundle. Under severance, if the secret manager or a baseline source is unreachable the gate
fails **closed** (REQUIRE_HUMAN) — do not proceed autonomously; escalate.
