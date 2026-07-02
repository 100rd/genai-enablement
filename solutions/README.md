# Solutions

One solution lives here — no parallel iterations are kept.

## [`sre-harness/`](sre-harness/)

The deterministic safety core of the **AI SRE program**: autonomy tiers T1–T4, action-tier
table, change-validation gate (PROCEED / BLOCK / REQUIRE_HUMAN — no LLM), platform-graph
port with the Omniscience MCP adapter, offline eval harness, gate CLI with CI
integrations.

**The program definition — what AI SRE is, its seven layers, the two loops (IRL + SDLC
bridge), roles, metrics, and roadmap — lives at
[`docs/ai-sre-program.md`](../docs/ai-sre-program.md).**

## Removed iterations

- **`ai-incident-agent/`** (Dec 2025, LangGraph "smart pager") — removed 2026-07;
  superseded by the harness direction ("the harness is the product"). Its node design
  remains in git history as the donor spec for the layer-④ T1 reasoning agents; its
  `decision_nodes` are deliberately discarded — decisions belong to harness gates.
