---
name: vllm-high-latency
description: Use when vLLM p99 latency exceeds its SLO, the request queue depth grows, or inference nodes show GPU memory pressure — staged diagnostics and recovery with per-step autonomy tiers.
version: 0.1.0
tags: [sre, runbook, inference, vllm, gpu]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T3
license: MIT
# runbook extension namespace:
category: inference
severity: high
clusters: [gpu-inference]
---

# vLLM Inference High Latency

Runbook-type skill. Each step is tagged with the autonomy tier required to execute it
(platform glossary: T1 read-only auto · T3 requires explicit human approval). An agent
operating below a step's tier stops and escalates with its findings.

Converted from `platform-design/ai-sre/runbooks/vllm-high-latency.md`
(`auto_executable_steps: [1,2,3]` → T1; `approval_required_steps: [4,5]` → T3).

## Symptoms

- vLLM p99 latency exceeding SLO threshold
- Request queue depth growing
- GPU memory pressure on inference nodes

## Steps

### Step 1 — Check vLLM metrics [T1, auto]

```promql
vllm_num_requests_waiting{namespace="gpu-inference"}
vllm_avg_generation_throughput_toks_per_s{namespace="gpu-inference"}
vllm_gpu_cache_usage_perc{namespace="gpu-inference"}
```

A high `gpu_cache_usage_perc` alongside a growing `num_requests_waiting` indicates KV-cache
saturation rather than a compute shortfall — note which before choosing a remedy.

### Step 2 — Check GPU memory and utilization [T1, auto]

```bash
kubectl top pods -n gpu-inference --sort-by=memory | head -20
```

### Step 3 — Check for recent config changes [T1, auto]

```bash
git log --since="4h" --oneline -- apps/gpu-inference/vllm/
```

Correlate: if a config change landed shortly before the latency rose, suspect the change
first — report the correlation before scaling or editing the cache config.

### Step 4 — Scale up vLLM replicas [T3, requires human approval]

State-changing but reversible (scale back down). Present Steps 1–3 findings with the
approval request.

```bash
kubectl scale deployment/vllm-inference -n gpu-inference --replicas={target_replicas}
```

### Step 5 — Adjust KV cache configuration [T3, requires human approval]

Disruptive: editing the configmap triggers pod restarts. Requires separate approval from
Step 4 — do not bundle.

```bash
kubectl edit configmap vllm-config -n gpu-inference
```

## Escalation

If Steps 1–3 do not identify a cause, or latency persists after scaling and cache tuning,
escalate to the platform team with the full diagnostic bundle instead of retrying.
