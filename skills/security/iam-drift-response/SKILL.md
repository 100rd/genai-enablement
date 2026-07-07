---
name: iam-drift-response
description: Use when an `iam_policy_drift` Sentinel finding fires — live IAM grants differ from the approved baseline (a set-difference of grants). Staged response (reproduce, classify, advise, revert via IaC, verify) with per-step autonomy tiers. NOT for secret-leak or CVE-in-SBOM findings.
version: 0.1.0
tags: [security, runbook, iam, drift, incident-response]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T3
license: MIT
# runbook extension namespace:
category: iam-drift
severity: high
trigger: iam_policy_drift Sentinel finding (per ADR-0008 S1)
---

# IAM Drift Response

Runbook-type skill. Each step is tagged with the autonomy tier required to execute it
(platform glossary: T1 read-only auto · T2 advisory — recommend, a human acts · T3 requires
explicit human approval within a window). An agent operating below a step's tier stops and
escalates with its findings.

Seeded from ADR-0008 build order S3 — the `security/` response runbook for
the `iam_policy_drift` Sentinel detector family (ADR-0008 S1: live IAM grants minus an approved
baseline — a set-difference, structurally identical to `new_error_signature`; severity by
action/resource sensitivity, wildcard / privilege-escalation → CRITICAL; confidence 1.0).
**ADR-0008 is accepted on `main`; the detector is not yet built; detector capabilities below
are design-stage.** Maps to the SIRL loop (per ADR-0008 program): DETECTED → TRIAGED
(Steps 1–2) → advice (Step 3) → ERADICATED via IaC PR (Step 4) → verify (Step 5).

## Trigger

- `iam_policy_drift` Sentinel detector finding — the set-difference of live IAM grants minus the
  approved baseline is non-empty.

## Steps

### Step 1 — Reproduce the diff (live − baseline) [T1, auto]

Read-only. Pull the live grants and the approved baseline and compute the set-difference the
detector reported. **Baseline is read from platform-design's policy substrate — read-only; this
domain consumes it, never authors it** (ADR-0008 Boundaries).

```bash
# live grants (read-only) — via the IAM inventory / Omniscience, or direct AWS as fallback
aws iam get-account-authorization-details > live.json
# baseline from the policy repo / substrate (read-only); drift = live − baseline
# (structurally: the grants present live that are absent from baseline)
```

Confirm the drifted grants reproduce. A baseline that is simply stale (an approved change not
yet merged to baseline) is a bookkeeping fix, not an incident — record and route to update the
baseline.

### Step 2 — Classify severity [T1, auto]

Use the **same logic the detector uses** (ADR-0008 S1) — decide from the drifted
grants' actions and resources:

- **Wildcard** (`Action: "*"` or `Resource: "*"`) or **privilege-escalation** actions
  (`iam:PassRole`, `iam:CreatePolicyVersion`, `iam:Attach*Policy`, `sts:AssumeRole` widening)
  → **CRITICAL / high**.
- Narrow, read-only additions on a non-sensitive resource → low.

Record the classification and the exact grants that drove it.

### Step 3 — Advise the revert [T2, advisory]

Recommend the precise change that returns live to baseline — which statements/grants to remove.
Flag if the drift looks adversarial (grants that widen privilege or add a new principal), in
which case containment (disable the suspicious principal — a T3 action) may precede the durable
revert. A human decides; this step only proposes.

### Step 4 — Revert via IaC PR [T3, requires human approval]

The durable revert is a **PR to the baseline / IaC repo** — **never a direct console or API
mutation of IAM.** platform-design **owns the policy substrate**; the correction lands as a
reviewed change to that baseline (ADR-0008 Boundaries + D9), passing the same
gates. Reverting *narrows* privilege back to baseline; **never broaden** an IAM policy and
**never widen** a security group — both are NEVER-T4.

```bash
# Open a PR against the policy/IaC baseline that removes the drifted grants.
# Do NOT `aws iam put-*` / edit in console — the substrate is changed only via reviewed IaC.
```

### Step 5 — Verify drift cleared on next scan [T1, auto]

Re-run `iam_policy_drift` after the IaC PR LANDS; confirm the set-difference (live − baseline)
is empty. Only then is the drift eradicated.

## Hard constraints (NEVER-T4 — non-amendable by agents; ADR-0008 D6)

- **Never broaden an IAM policy** or **widen a security group / firewall** (both NEVER-T4). The
  only correction here is *narrowing* back to baseline.
- **Never mutate IAM directly** (console / `put-*` API) — the revert is a reviewed **IaC PR** to
  platform-design's baseline; this domain never authors the substrate.
- **Never touch the platform-design security substrate** (Cedar / OPA / Kyverno / KMS) directly.
- **Never disable or modify audit logging / CloudTrail** (NEVER-T4).
- **Never disable the detector** to silence the finding (NEVER-T4).

## Escalation

If the drift is adversarial (unexplained privilege-escalation grants, a new unknown principal),
escalate to **SecOps on-call** immediately and preserve forensic evidence before any
containment (ADR-0008 D7). Under severance, if the baseline source is
unreachable the security gate fails **closed** (REQUIRE_HUMAN); the detector degrades **open** to
a direct source on a least-privilege fallback credential with liveness monitored — do not assume
"no drift" from a silent detector.
