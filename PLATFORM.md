# Synchronized platform

This is the canonical entry point for work spanning `genai-enablement`, `Barbarossa`, `omnius`,
`Omniscience`, and `platform-portal`.

- Read the [full synchronized-platform plan](docs/synchronized-platform/README.md) for the
  cross-repository ADR order, component boundaries, work packages, and current gates. Its stable
  repository URL is
  <https://github.com/100rd/genai-enablement/blob/main/docs/synchronized-platform/README.md>.
- Read [the machine-readable registry](portfolio/synchronized-platform.json) when tooling needs the
  exact ADR, capability-SPEC, and task-SPEC inventory.
- The first accepted deployment selection is
  [`management-readonly-v1`](docs/synchronized-platform/profiles/management-readonly-v1.md):
  Omniscience, Barbarossa Reliability, and Platform Portal; Omnius remains a target component but is
  deferred from the runtime and all effects are disabled. Barbarossa production execution is Go under
  [ADR-0022](docs/decisions/0022-barbarossa-go-production-runtime.md); TypeScript is migration-only
  conformance evidence.
- The next accepted preparation layer is
  [`barbarossa-ha-v1`](docs/synchronized-platform/profiles/barbarossa-ha-v1.md) under
  [ADR-0023](docs/decisions/0023-barbarossa-full-go-distributed-ha-runtime.md): complete Go migration,
  fenced distributed work, Barbarossa HA, read-only Portal detail and independent failure qualification.
- The accepted developer launch profile is
  [`management-readonly-local-v1`](docs/synchronized-platform/profiles/management-readonly-local-v1.md)
  under [ADR-0024](docs/decisions/0024-management-readonly-local-compose-profile.md): real owner
  services composed from independently runnable fragments, selected-owner mocks absent, and functional
  smoke explicitly separated from HA/deployment qualification.
- Execute work from the owning component's local capability or task SPEC. This repository coordinates
  the plan; it does not replace component requirements, probes, or evidence.

## Component entry points

| Component | Local entry point | Owned contracts |
|---|---|---|
| `genai-enablement` | this file | cross-repository ADRs, PII Wall governance, synchronized work order, and reusable Autonomous SRE harness SPECs |
| `Barbarossa` | [`../Barbarossa/PLATFORM.md`](../Barbarossa/PLATFORM.md) in the sibling workspace; planned [repository link](https://github.com/100rd/Barbarossa/blob/main/PLATFORM.md) | Continuous Management kernel and independently assignable Reliability, Cost & Value, AI assurance, security, privacy, compliance, supply-chain, delivery, knowledge, capacity, toil, and product-outcome SPECs |
| `omnius` | [`../omnius/PLATFORM.md`](../omnius/PLATFORM.md) in the sibling workspace; [repository link](https://github.com/100rd/omnius/blob/main/PLATFORM.md) | governed factory capability/task SPECs, context/egress PII enforcement, and readiness profiles |
| `Omniscience` | [`../Omniscience/PLATFORM.md`](../Omniscience/PLATFORM.md) in the sibling workspace; [repository link](https://github.com/100rd/Omniscience/blob/main/PLATFORM.md) | knowledge-plane capability/task SPECs, ingestion/lifecycle PII enforcement, and execution evidence |
| `platform-portal` | [`../platform-portal/PLATFORM.md`](../platform-portal/PLATFORM.md) in the sibling workspace; [repository link](https://github.com/100rd/platform-portal/blob/main/PLATFORM.md) | federated visualization, Continuous Management Center, Privacy Center, component detail, and owner-delegated control SPECs |

An agent assigned one component must stay in that component's writable scope. Cross-repository outcomes
are split into the independently claimable work packages defined by the full plan.

For the initial deployment handoff, dispatch SP-90 in Barbarossa and SP-86 in Omniscience independently;
after both receipts exist, dispatch SP-87 in Barbarossa, SP-88 in Platform Portal, and finally SP-89
here for independent non-production qualification. None of those
tasks authorizes infrastructure mutation or production activation.

For the HA follow-on, dispatch SP-91 after exact SP-87 binding full-Go SP-90; dispatch SP-92 after SP-91;
dispatch SP-93 after SP-88/SP-92; and dispatch SP-94 after SP-89/SP-92/SP-93 plus a named
non-production authority receipt. The queue distributes at-least-once work; Barbarossa's durable store
and fencing protocol remain authoritative. Portal has no broker/store credentials or queue controls.

For local launch, dispatch SP-95 in Omniscience and SP-96 in Barbarossa concurrently after their exact
owner inputs; dispatch SP-97 in Platform Portal after both local receipts plus SP-88/SP-93; then
dispatch SP-98 here to assemble and qualify the disposable Compose application. A local receipt is
`development-single-host`, never SP-89/SP-92/SP-94 evidence or activation authority.
