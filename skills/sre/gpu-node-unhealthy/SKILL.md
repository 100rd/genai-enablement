---
name: gpu-node-unhealthy
description: Use when a GPU node reports DCGM XID errors, GPU utilization drops to 0%, or pods fail to schedule on GPU nodes — staged diagnostics and recovery with per-step autonomy tiers.
version: 0.1.0
tags: [sre, runbook, gpu, kubernetes]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T3
license: MIT
# runbook extension namespace:
category: gpu-health
severity: high
clusters: [gpu-inference, gpu-analysis]
---

# GPU Node Unhealthy Response

Runbook-type skill. Each step is tagged with the autonomy tier required to execute it
(platform glossary: T1 read-only auto · T3 requires explicit human approval). An agent
operating below a step's tier stops and escalates with its findings.

Converted from `platform-design/ai-sre/runbooks/gpu-node-unhealthy.md`
(`auto_executable_steps: [1,2,3]` → T1; `approval_required_steps: [4,5]` → T3).

## Symptoms

- DCGM XID errors detected
- GPU utilization drops to 0%
- Pod scheduling failures on GPU nodes

## Steps

### Step 1 — Gather GPU diagnostics [T1, auto]

```bash
kubectl describe node {node} | grep -A 20 "Allocated resources"
kubectl logs -n gpu-operator -l app=nvidia-dcgm-exporter --tail=100
```

### Step 2 — Check recent deployments [T1, auto]

```bash
git log --since="2h" --oneline -- apps/gpu-inference/
```

Correlate: if a deployment landed shortly before the symptoms, suspect the change first —
report the correlation before touching the node.

### Step 3 — Verify GPU operator status [T1, auto]

```bash
kubectl get pods -n gpu-operator -o wide
```

### Step 4 — Cordon node [T3, requires human approval]

State-changing but reversible (`kubectl uncordon`). Present Steps 1–3 findings with the
approval request.

```bash
kubectl cordon {node}
```

### Step 5 — Drain and replace node [T3, requires human approval]

Disruptive: evicts workloads. Requires separate approval from Step 4 — do not bundle.

```bash
kubectl drain {node} --ignore-daemonsets --delete-emptydir-data
```

## Escalation

If Steps 1–3 do not identify a cause, or symptoms persist after node replacement, escalate
to the platform team with the full diagnostic bundle instead of retrying.
