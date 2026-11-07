# Runtime profile: management-platform-frankfurt-v1

Status: implementation in progress; not activated or qualified.

User-confirmed target: AWS account `120736097561`, region `eu-central-1`,
EKS `nonprod-euc1`, all namespaces. The architecture is cloud agnostic:
AWS Config is not a dependency and will not be enabled for this work.
Direct cloud API adapters and Kubernetes collectors feed Omniscience.
Cloud/account/region identifiers belong to adapter configuration and resource
identity, not to Barbarossa's generic assessment logic.

Implementation follows the [platform-state delivery plan](../platform-state-plan.md).
Collection is hybrid: pull/reconcile plus watch/events, durable push to the owner,
and pinned owner reads by Barbarossa. The limited self-platform vertical slice and
full Frankfurt coverage have separate acceptance gates.

## Required behavior

- Omniscience represents pinned desired state, observed resources, operational signals,
  relationships, change history, timestamps, source identity
  and explicit collection coverage. Credentials and Secret payloads are excluded.
- Collectors distinguish complete, partial, denied, failed and stale collection.
  An absent item is not proof of deletion after an incomplete collection.
- Kubernetes watches and periodic reconciliation cover all namespaces. AWS
  collectors use paginated regional read APIs. Coverage lists unsupported and
  inaccessible resource types instead of claiming the entire account is healthy.
- Barbarossa consumes owner evidence for Reliability and Security, freezes its
  references into analysis jobs and retains cases, assessments and history.
  Model output remains non-authoritative; remediation is not enabled.
- Security evaluates observed access/exposure/configuration evidence. Missing
  telemetry does not establish compliance. Vulnerability scanning requires its
  own source and is not implied by configuration checks.
- Portal Observe displays current owner knowledge, timestamps and coverage;
  Control displays cases, analysis queue, runner, results and recommendations.
- A separate profile/database binding preserves the local profile and its
  historical receipts. Cluster placement must not be described as shared-host.

## Acceptance gates

1. Close the deployment findings in the EKS audit, preserving existing data.
2. Prove real collection → Omniscience → tenant-scoped Portal reads; reproduce
   resource updates and deletions without duplicate entities or cross-tenant data.
3. Demonstrate a bounded Reliability fault and a non-destructive Security finding
   through case → real Codex analysis → Portal → observed recovery.
4. Demonstrate collection loss, denied access and stale evidence as unknown or
   degraded; preserve history and call budgets through process/Pod replacement.
5. Retain analysis-only execution, fenced leases, evidence validation and limits;
   no infrastructure credentials reach the model process.
6. Report actual API/resource coverage and remaining gaps. A partial inventory
   is useful progress but cannot close the requested platform-wide acceptance.

## Current evidence

Initial direct API collection succeeded for 6 EC2 instances, 2 VPCs, 8 security
groups, 1 EKS cluster, 1 load balancer, 1 RDS instance and 120 Kubernetes Pods. Lambda returned
an empty list. This is a partial private snapshot, not yet an Omniscience ingestion
receipt. AWS Config has no configured recorder and is not being enabled.

Simple implementation tasks use gpt-6-luna; state/integration tasks use
gpt-6.1-sol. Each slice requires lead diff/test verification and independent code
review. Deployment, source completion and acceptance are recorded separately.

The cloud-neutral evidence wire contract is implemented and source-reviewed in
Omniscience. Receipt persistence, its authorized API, scheduled publication and
Barbarossa intake remain separate work. See [source checks](../releases/management-platform-frankfurt-v1/source-checks/verification.json); these do not qualify the deployed stack.
