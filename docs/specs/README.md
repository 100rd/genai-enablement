# genai-enablement SPEC and task index

Platform-wide context and cross-repository dependencies live in the canonical
[`PLATFORM.md`](../../PLATFORM.md) entry point. This directory remains the authoritative local execution
catalog for `genai-enablement`; an agent can claim one SPEC or ready task here without writable access
to a sibling repository.

## Synchronized-platform governance contracts

| Contract | Status | Work package | Development boundary |
|---|---|---|---|
| [SPEC-PII-POLICY](SPEC-PII-POLICY-platform-policy-contract.md) | `ready` | `SP-60` | portable schemas, fixtures, validator and compatibility only |
| [task-sp-60-pii-policy-contract-v1](task-sp-60-pii-policy-contract-v1.md) | `ready` | `SP-60` | materialize the non-active PII contract bundle |
| [task-sp-70-continuous-management-contract-release](task-sp-70-continuous-management-contract-release.md) | `ready` | `SP-70` | close owner-contract discovery and registry compatibility |

`ready` here authorizes only the exact repository-local development scope written in the task. It does
not publish a live policy, activate a management loop, provision trust, call a provider, mutate a sibling
repository, deploy, or grant production authority.

## Autonomous SRE harness catalog

The Track-B implementation follows evidence-gated capability SPECs. A SPEC is the behavioral oracle for
code and tests; the roadmap orders the work but does not replace the component contract. All SPECs remain
Draft, non-authorizing construction artifacts until a human makes the applicable readiness decision and
their own external/live evidence exists.

## Definition of a complete Track-B SPEC

Every source SPEC in this directory has the same mandatory execution handoff:

1. capability type, Draft status, component owner, governing decisions, roadmap gate, and dependencies;
2. exact local evidence scope, operational state, next external gate, and negative authority boundary;
3. bounded intent/user journey, inputs/outputs, and explicit out-of-scope behavior;
4. contiguous stable `REQ-*` requirements with fallback behavior;
5. portable interfaces plus one contiguous `P-*` acceptance-probe family;
6. an exact source-digest traceability manifest joining every probe to existing pytest nodes and bounded
   implementation paths; and
7. explicit exit evidence that local fixtures/tests cannot satisfy.

This makes the catalog complete enough for agent planning and implementation review. It does **not** move
any SPEC from `draft` to `ready`: under ADR-0009 that transition belongs to a human/CODEOWNER, and the
listed live gates remain blocked.

The machine-readable `track_b_spec_backlog` in
[`portfolio/projects.json`](../../portfolio/projects.json) covers all and only these thirteen source
SPECs, including the previously implicit B0 eval baseline, Sentinel core, and the two early detector
families. Its status is `external-evidence-required`: it rejoins the source id, path, status, roadmap
gate, dependencies, contiguous REQ/probe counts, and exact next gate. Dependencies order work and
operational qualification; they do not retroactively authorize construction. The combined local planning
evidence does not authorize a provider call, live credential, deployment, remediation, pilot, or
production-readiness claim.

The thirteen checked portable traceability slices are
[`SPEC-B0`](../../solutions/sre-harness/spec-traceability/SPEC-B0.json),
[`SPEC-B1`](../../solutions/sre-harness/spec-traceability/SPEC-B1.json),
[`SPEC-B2`](../../solutions/sre-harness/spec-traceability/SPEC-B2.json),
[`SPEC-B3`](../../solutions/sre-harness/spec-traceability/SPEC-B3.json),
[`SPEC-B4`](../../solutions/sre-harness/spec-traceability/SPEC-B4.json),
[`SPEC-B5`](../../solutions/sre-harness/spec-traceability/SPEC-B5.json),
[`SPEC-B6`](../../solutions/sre-harness/spec-traceability/SPEC-B6.json),
[`SPEC-B7-CORE`](../../solutions/sre-harness/spec-traceability/SPEC-B7-CORE.json),
[`SPEC-B7`](../../solutions/sre-harness/spec-traceability/SPEC-B7.json),
[`SPEC-B7-NES`](../../solutions/sre-harness/spec-traceability/SPEC-B7-NES.json),
[`SPEC-B7-CIR`](../../solutions/sre-harness/spec-traceability/SPEC-B7-CIR.json),
[`SPEC-B7-DRIFT`](../../solutions/sre-harness/spec-traceability/SPEC-B7-DRIFT.json), and
[`SPEC-B7-SAT`](../../solutions/sre-harness/spec-traceability/SPEC-B7-SAT.json). Their registry fields
bind each exact source digest and every source probe id to existing pytest nodes and implementation files.
No row retains a null manifest. This is static `local-portable-only` traceability, not a cached PASS,
live evidence, completion claim, or authorization.
Traceability registry summary: `13` checked manifests; `0` remaining null.

| SPEC | Gate | Source status | REQ / probes | Requires | Evidence scope | Operational state | Next gate |
|---|---|---|---:|---|---|---|---|
| [SPEC-B0](SPEC-B0-offline-eval-harness.md) | `B0` | `draft-portable-construction` | `8` / `8` | — | `local-construction-only` | `incomplete` | `human-corpus-and-regression-policy-publication` |
| [SPEC-B1](SPEC-B1-read-only-triage-rca.md) | `B1` | `draft-construction` | `9` / `9` | `SPEC-B0` | `local-construction-only` | `incomplete` | `approved-sources-analyzer-and-real-corpus` |
| [SPEC-B2](SPEC-B2-advisory-change-validation-integration.md) | `B2` | `draft-construction` | `9` / `9` | `SPEC-B0` | `local-construction-only` | `incomplete` | `approved-consumer-and-observed-advisory-run` |
| [SPEC-B3](SPEC-B3-deterministic-canary-rollback.md) | `B3` | `draft-construction` | `9` / `9` | — | `local-construction-only` | `incomplete` | `human-policy-and-live-canary-qualification` |
| [SPEC-B4](SPEC-B4-tier4-allowlisted-remediation.md) | `B4` | `draft-construction` | `10` / `10` | — | `local-construction-only` | `incomplete` | `human-allowlist-and-live-provider-drills` |
| [SPEC-B5](SPEC-B5-tier3-hitl-remediation.md) | `B5` | `draft-construction` | `10` / `10` | — | `local-construction-only` | `incomplete` | `human-authority-and-live-provider-drills` |
| [SPEC-B6](SPEC-B6-permanent-fix-chase.md) | `B6` | `draft-portable-construction` | `10` / `10` | `ADR-0003`, `SPEC-B1`, `SPEC-B5` | `local-construction-only` | `incomplete` | `human-policy-and-live-provider-drills` |
| [SPEC-B7-CORE](SPEC-B7-core-sentinel-runtime-contract.md) | `B7` | `draft-portable-construction` | `8` / `8` | `SPEC-B0` | `local-construction-only` | `incomplete` | `human-runtime-source-and-operations-policy` |
| [SPEC-B7](SPEC-B7-error-rate-baseline-detector.md) | `B7` | `draft-portable-construction` | `9` / `9` | `SPEC-B0`, `SPEC-B7-CORE` | `local-construction-only` | `incomplete` | `human-policy-source-and-live-calibration` |
| [SPEC-B7-NES](SPEC-B7-new-error-signature-detector.md) | `B7` | `draft-portable-construction` | `8` / `8` | `SPEC-B0`, `SPEC-B7-CORE` | `local-construction-only` | `incomplete` | `human-policy-source-and-live-calibration` |
| [SPEC-B7-CIR](SPEC-B7-change-induced-regression-detector.md) | `B7` | `draft-portable-construction` | `10` / `10` | `SPEC-B0`, `SPEC-B7`, `SPEC-B7-CORE` | `local-construction-only` | `incomplete` | `human-policy-source-and-live-calibration` |
| [SPEC-B7-DRIFT](SPEC-B7-drift-detector.md) | `B7` | `draft-portable-construction` | `10` / `10` | `SPEC-B0`, `SPEC-B7-CORE` | `local-construction-only` | `incomplete` | `human-policy-source-and-live-calibration` |
| [SPEC-B7-SAT](SPEC-B7-saturation-expiry-detector.md) | `B7` | `draft-portable-construction` | `9` / `9` | `SPEC-B0`, `SPEC-B7-CORE` | `local-construction-only` | `incomplete` | `human-policy-source-and-live-calibration` |

Passing portable tests proves only contract conformance. It does not bind a live provider, approve a
model, expose a write tool, deploy the harness, or prove incident-response usefulness.
