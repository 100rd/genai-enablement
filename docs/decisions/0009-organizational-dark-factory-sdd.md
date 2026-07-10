# ADR-0009: Organizational Dark Factory uses ADR-to-SPEC governance

- **Status:** Proposed
- **Date:** 2026-07-10
- **Deciders:** platform owner
- **Scope:** cross-repo (genai-enablement decision plane; omnius governed execution;
  multiqlti proving ground; platform-portal presentation)
- **Builds on:** [ADR-0002](0002-platform-skills-registry.md),
  [ADR-0003](0003-unified-sdlc-standard.md),
  [ADR-0004](0004-experience-plane.md),
  [ADR-0005](0005-autonomous-factory-intake.md), and
  [ADR-0006](0006-unified-loop-decision-model.md)
- **Vocabulary:** terms as defined in [platform-glossary.md](../platform-glossary.md)

## Context

The platform already has the parts of a governed organizational Dark Factory:

- ADR-0003 defines one quality-gated lifecycle and Definition of Done.
- ADR-0005 makes a committed specification the unit of work and separates spec approval
  from code landing.
- ADR-0006 defines how every load-bearing branch is decided.
- omnius has a constitution, segmented capability specifications, deterministic gates,
  and a conformance oracle.

What was not yet explicit is the **authority boundary between human decisions and agent
execution**. Without that boundary, an agent can be given an architecture discussion,
ticket, or broad ADR and be expected to infer its own executable contract. That creates
three failure modes:

1. **Intent drift:** implementation choices silently become architecture decisions.
2. **Self-authored correctness:** the producer invents or weakens the criteria that judge it.
3. **Document ambiguity:** an ADR, a capability contract, and a task plan all look like
   interchangeable markdown even though they carry different authority.

For an organizational factory, this is a governance problem rather than a prompt-quality
problem. The factory needs an explicit compiler boundary: humans decide; specifications
make those decisions executable; agents operate only inside accepted specifications.

## Decision

Adopt **ADR-to-SPEC governance** as the platform's Spec-Driven Development (SDD) model.

> **ADRs are the human decision plane. SPECs are the agent execution plane.**

An accepted ADR establishes intent, boundaries, ownership, alternatives, and consequences.
One or more accepted SPECs translate that decision into requirements, interfaces, fallbacks,
acceptance probes, and evidence obligations. Agents may implement only from a ready SPEC.

### D1 - Four artifact classes, four authorities

| Artifact | Primary audience | Owns | Does not own |
|---|---|---|---|
| **Cross-repo ADR** | human platform owners | decisions spanning two or more components | component implementation details |
| **Component ADR** | human component owners | local adoption and irreversible component choices | executable acceptance logic |
| **Capability SPEC** | agents and reviewers | buildable system behavior, REQs, contracts, fallbacks, probes | organizational rationale or new boundaries |
| **Task SPEC** | one execution loop | bounded work envelope and acceptance criteria for one change | architecture policy or reusable capability design |

Cross-repo ADRs live in `genai-enablement/docs/decisions/`. Component ADRs and capability
SPECs live with the owning component. Committed task SPECs live in that component's
`docs/specs/` queue per ADR-0005.

### D2 - The normative flow is ADR -> capability SPEC -> task SPEC -> evidence

```text
human concern / proposal
  -> ADR draft
  -> human acceptance
  -> capability SPEC set
  -> human readiness approval
  -> committed task SPEC(s)
  -> agent execution
  -> independent verification evidence
  -> landing gate
  -> observed outcome / escape join
```

Code may not be the first durable artifact for a new boundary or capability. A change that
touches two or more components starts with a cross-repo ADR. A component-local irreversible
decision starts with a component ADR. Routine work inside an already-accepted boundary may
start from a task SPEC that cites the governing ADR and capability SPEC.

### D3 - Traceability is mandatory and bidirectional

Every capability SPEC declares `Governing ADRs`. Every task SPEC declares both
`governingAdrs` and `capabilitySpecs`. Each `REQ-*` has stable acceptance probe ids, and
every evidence record identifies the exact REQ and task SPEC revision it satisfies.

The reverse direction is also required: an ADR maintains an implementation map of the
capability SPECs that realize it. An ADR is not considered **realized** merely because all
listed files exist; the human owner closes it only after its required evidence is present.

Orphan code, orphan SPECs, and unimplemented ADR decisions are mechanically detectable states,
not review-time conventions.

### D4 - Readiness is human-owned; execution is machine-enforced

Artifact states are distinct:

```text
ADR:       proposed -> accepted -> superseded
Capability SPEC: draft -> ready -> implemented -> verified -> superseded
Task SPEC: draft -> ready -> in-progress -> landed -> observed -> done
                                           \-> failed / rejected / expired
                                           \-> escaped (post-landing outcome)
```

Only a human/CODEOWNER may move an ADR to `accepted` or a SPEC to `ready`. Only the
conformance/evidence path may move a capability SPEC to `verified`. Only the lifecycle and
landing gates may move a task SPEC beyond `in-progress`. Agents may propose state changes;
they never authorize their own readiness or verification.

### D5 - Every requirement is executable or explicitly fail-closed

Every capability `REQ-*` carries:

1. a deterministic acceptance probe or a typed placeholder that fails closed;
2. the expected result and evidence shape;
3. the source of ground truth, external to the producer;
4. a fallback for unavailable dependencies or an explicit `Fallback: none`;
5. an owner for any human-held decision or deferred constant.

Unmeasurable is not pass. A missing probe is not a waiver. Temporary deferral uses the
existing explicit human waiver mechanism and remains visible as debt.

### D6 - The producer cannot redefine its oracle

The execution identity may not modify, in the same loop:

- its governing ADRs;
- its task SPEC's accepted scope or acceptance criteria;
- golden sets, acceptance probes, or verifier policy;
- autonomy policy, CODEOWNERS, registry locks, or waiver state.

If implementation discovers that any of these must change, the loop parks and emits a
**decision-return** containing the evidence and proposed amendment. A human decides whether
to revise the ADR, revise the SPEC, split the task, or reject the work. Resumption starts
from a new immutable SPEC revision and repeats classification.

### D7 - SPEC compilation is deterministic and mechanism-independent

The platform will validate and normalize SPECs into a structured task envelope before an
engine sees them. The normalized envelope includes at least:

```yaml
task_id: stable-id
spec_revision: git-sha
intent: human-readable statement
task_class: R0|A|B|C|E
autonomy_tier: T1|T2|T3|T4
scope: {}
role: standing-role-id
skills: []
acceptance_criteria: []
rollback: {}
source: {}
```

The validator checks schema, references, readiness, immutable revision, and the presence of
acceptance probes. Classification and tier assignment remain deterministic gate decisions;
frontmatter requests are inputs, never authority. Unknown or conflicting values route to a
human gate.

The normalized contract is shared; engines remain independent. multiqlti may execute it as
a Consilium/DAG loop, while omnius executes it as a durable FSM.

### D8 - Organizational rollout is vertical and evidence-gated

The organization does not enable a general-purpose autonomous factory at once. It admits one
task class and one Standing Role through this sequence:

1. assess the target team and collect baseline delivery/safety metrics;
2. accept the task-class ADR and capability SPECs;
3. run task SPECs with human landing required;
4. measure verifier-alone quality, counterfactual escapes, cost, and human curation time;
5. widen autonomy or add task classes only by a new human decision backed by that evidence.

The first omnius class remains reversible Terraform-module work in non-production. Priority
changes queue position, never gate requirements.

### D9 - Component boundaries remain intact

SDD coordinates the platform; it does not collapse it:

- **genai-enablement** owns cross-repo ADRs, vocabulary, and shared artifact contracts.
- **omnius** owns governed execution, component SPECs, task execution, and its local cockpit.
- **Omniscience** owns platform state and remains a severable read-only dependency.
- **skills registry** owns skill content and lock hashes; runtime trust remains local.
- **platform-portal** projects state and deep-links to owners; it never decides.

No component copies another component's source of truth to make SDD convenient.

### D10 - SDD depth is graded by decision risk

SDD is mandatory, but its document weight is proportional to the decision being made:

| Mode | Use when | Required authority |
|---|---|---|
| **Quick** | R0 exploration or a reversible edit with no new boundary, side effect, oracle, or policy | lightweight task SPEC citing the existing capability contract |
| **Standard** | routine implementation inside an accepted capability and task class | complete task SPEC with registered acceptance probes |
| **Full** | new capability/boundary, cross-repo contract, new side effect, Class B/C/E work, oracle or autonomy change | accepted ADR + ready capability SPEC + task SPEC |

Classification is deterministic and may only move work to a heavier mode. An agent cannot select a
lighter mode to avoid a human decision. Quick mode reduces ceremony, not traceability: it still records
intent, provenance, scope, completion criteria, and the immutable execution revision.

### D11 - Assurance is progressive, cumulative, and threat-driven

The factory does not require every production-grade mechanism before proving its first useful vertical.
Each task runs under a declared cumulative assurance profile:

| Profile | Minimum claim |
|---|---|
| **P0 Control-plane MVP** | immutable ready SPEC, isolated worker, default-deny network, external deterministic verification, Draft PR, human merge, canonical outcome |
| **P1 Governed** | P0 + durable replay/idempotency, separate verifier, pinned skills, deterministic policy adapter, canonical telemetry |
| **P2 High Assurance** | P1 + threat-model-selected hardened sandbox, workload identity and leased secrets where required, independent verifier host, adversarial isolation/tamper probes |
| **P3 Scale & Autonomy** | P2 + Standing Roles, Experience, trust cohorts, and evidence-earned per-class auto-merge |

Profiles are floors, not product editions. A higher profile includes every lower-profile obligation.
Profile selection follows the versioned threat model and task classification; product fashion or a named
technology is not sufficient justification for a control. Activating a higher profile or making a claim
that it is met is a human-owned, evidence-gated transition.

### D12 - Merge conformance and assurance certification are distinct gates

The platform exposes two results rather than overloading one permanently red check:

1. **Contract conformance** is the required merge check. It fails on regressions, invalid artifacts,
   missing probes for requirements claimed as implemented, or violation of the active profile.
2. **Assurance certification** reports whether a target profile is RED, AMBER, or GREEN. Missing real
   enforcement remains visible and cannot be called pass, but blocks profile activation, production
   promotion, autonomy widening, and auto-merge rather than every repository change.

This preserves fail-closed behavior at the risk transition. It also prevents a future-control placeholder
from making routine development depend on recurring administrator bypasses. A component may not weaken a
non-waivable invariant by relabeling it; it may only truthfully declare that the corresponding higher
profile has not yet been certified.

## Consequences

**Positive**

- Humans get a reviewable decision surface that does not require reading execution detail.
- Agents get bounded, machine-checkable contracts instead of architectural prose.
- Every implementation can be traced to a human decision and every decision to evidence.
- Discoveries that change intent return to humans rather than leaking into code as policy.
- The same contract supports the personal and governed factories without a shared engine.

**Costs / risks**

- Spec approval adds deliberate latency before execution.
- Weakly written acceptance criteria become an explicit bottleneck rather than hidden agent
  ambiguity; curation capacity must be staffed and measured.
- The schema, traceability index, and conformance probes become governed product surfaces.
- Over-specification can slow R0 exploration; R0 task SPECs therefore remain lightweight but
  still carry intent, provenance, and completion criteria.
- Progressive profiles require explicit claim language; a P0 success cannot be presented as P2 security.
- Two gate outputs add policy surface, but remove the incentive to normalize permanent merge overrides.

## Alternatives considered

1. **ADRs directly executed by agents** - rejected: ADRs explain decisions but intentionally
   omit the bounded, testable detail required for safe execution.
2. **Tickets as executable contracts** - rejected by ADR-0005: tracker payloads are mutable,
   inconsistent, and not a uniform source of reviewed intent.
3. **Agents author and approve their own SPECs** - rejected: this collapses producer and oracle.
4. **One universal document type** - rejected: it obscures authority and makes state transitions
   ambiguous.
5. **One shared factory engine** - rejected by ADR-0003/0006: shared invariants and decisions are
   required; shared implementation is not.

## Adoption map

omnius adopts this ADR through local component ADRs and six initial capability SPECs:

| Capability | Responsibility |
|---|---|
| `SPEC-IN` | committed-spec intake, validation, readiness, tracker write-back |
| `SPEC-ROLE` | Standing Roles and ephemeral-loop spawning |
| `SPEC-EXP` | verification-grounded Experience plane |
| `SPEC-REG` | pinned platform-skills registry consumption and local trust |
| `SPEC-OT` | canonical OutcomeEvent / ReturnEvent and traceability joins |
| `SPEC-TM` | threat model, assurance-profile selection, control mapping, and certification |

These SPECs extend existing omnius capabilities; they do not replace SPEC-CD, SPEC-HB,
SPEC-MEM, SPEC-SK, SPEC-FO, or SPEC-OS.

## Verification

Platform-level conformance fixtures must prove:

- an unaccepted ADR cannot authorize a ready capability SPEC;
- a task SPEC with missing/invalid references cannot enter execution;
- an execution identity cannot change its accepted criteria or oracle paths;
- a decision-return parks the task and a new SPEC revision triggers reclassification;
- evidence resolves to an exact task revision and `REQ-*` id;
- a component can lose the coordination hub after materialization and continue the active
  task from its pinned local contract (severance), without accepting new unverified work.
- an R0 change selects Quick mode while a new boundary or Class B/C/E change selects Full mode;
- an agent request for a lighter SDD mode or assurance profile is widened or parked;
- a missing P2 control leaves P2 certification RED without failing a conformant P0 implementation PR;
- activation, production promotion, autonomy widening, and auto-merge fail closed unless the target
  assurance profile is certified.

## References

- [ADR-0003](0003-unified-sdlc-standard.md) - lifecycle and Definition of Done
- [ADR-0004](0004-experience-plane.md) - verification-grounded experience
- [ADR-0005](0005-autonomous-factory-intake.md) - committed SPEC and Standing Roles
- [ADR-0006](0006-unified-loop-decision-model.md) - branch decision rules
- omnius `specs/SPEC-CC-constitution.md` - fail-closed conformance meta-gate
- omnius `specs/SPEC-OS-correctness-curation.md` - human-owned correctness contracts
