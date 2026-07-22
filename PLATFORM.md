# Synchronized platform

This is the canonical entry point for work spanning `genai-enablement`, `Barbarossa`, `omnius`,
`Omniscience`, and `platform-portal`.

- Read the [full synchronized-platform plan](docs/synchronized-platform/README.md) for the
  cross-repository ADR order, component boundaries, work packages, and current gates. Its stable
  repository URL is
  <https://github.com/100rd/genai-enablement/blob/main/docs/synchronized-platform/README.md>.
- Read [the machine-readable registry](portfolio/synchronized-platform.json) when tooling needs the
  exact ADR, capability-SPEC, and task-SPEC inventory.
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
