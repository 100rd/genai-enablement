---
name: high-pod-restart-rate
description: Use when pod restart counts climb rapidly, pods enter CrashLoopBackOff, or containers are OOMKilled — staged diagnostics and recovery with per-step autonomy tiers.
version: 0.1.0
tags: [sre, runbook, kubernetes, workload-health]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T3
license: MIT
# runbook extension namespace:
category: workload-health
severity: medium
clusters: [gpu-inference, platform, blockchain, gpu-analysis]
---

# High Pod Restart Rate Investigation

Runbook-type skill. Each step is tagged with the autonomy tier required to execute it
(platform glossary: T1 read-only auto · T3 requires explicit human approval). An agent
operating below a step's tier stops and escalates with its findings.

Converted from `platform-design/ai-sre/runbooks/high-pod-restart-rate.md`
(`auto_executable_steps: [1,2,3]` → T1; `approval_required_steps: [4]` → T3).

## Symptoms

- Pod restart count increasing rapidly
- CrashLoopBackOff observed
- OOMKilled events

## Steps

### Step 1 — Identify crashing pods [T1, auto]

```bash
kubectl get pods -n {namespace} --sort-by='.status.containerStatuses[0].restartCount' | tail -20
```

### Step 2 — Check pod events and logs [T1, auto]

```bash
kubectl describe pod {pod} -n {namespace}
kubectl logs {pod} -n {namespace} --previous --tail=200
```

Read the previous container's logs and the pod events together: an OOMKilled last state
points at memory limits, a non-zero application exit code points at the workload itself.

### Step 3 — Check resource usage [T1, auto]

```sql
SELECT timestamp, pod, container, memory_usage_bytes, memory_limit_bytes
FROM k8s_pod_metrics
WHERE namespace = '{namespace}' AND timestamp > now() - INTERVAL 1 HOUR
ORDER BY memory_usage_bytes DESC LIMIT 20
```

Correlate: if usage is riding the limit before each restart, the cap is too low or the
workload is leaking — report which before proposing a rollback.

### Step 4 — Rollback deployment [T3, requires human approval]

State-changing but reversible (roll forward with a new revision, or `rollout undo` again).
Present Steps 1–3 findings with the approval request.

```bash
kubectl rollout undo deployment/{deployment} -n {namespace}
```

## Escalation

If Steps 1–3 do not identify a cause, or restarts persist after the rollback, escalate to
the platform team with the full diagnostic bundle instead of retrying.
