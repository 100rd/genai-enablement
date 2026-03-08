# AI Enablement Plan: Executive Summary

**Organization Profile**: Financial Services (Transaction Analysis, KYC/KYB)
**Compliance**: SOC 2 Type II, ISO 27001 (HIPAA not in scope)
**Primary Cloud**: AWS (multi-cloud GPU when needed)
**Regulators**: OCC / Federal Reserve (SR 11-7 mandatory)
**Team**: 20-50 engineers | Rust, Go, Node.js | GitLab CI + ArgoCD
**Observability**: Datadog (already deployed)
**KYC System**: In-house built
**Transaction Volume**: 100K - 1M/day
**Current AML False Positive Rate**: 90%+
**Date**: March 8, 2026 (v2.0 — org-specific refinements applied)
**Quality Gate**: Fact-checked (87 claims verified) + Peer-reviewed (8.2/10)

---

## The #1 Business Case: AML False Positive Reduction

Your 90%+ false positive rate on AML/fraud alerts is the strongest ROI driver. With in-house KYC and 100K-1M daily transactions, ML-based scoring can realistically reduce false positives to 20-40%, freeing analyst capacity by 3-5x.

**Before AI**: 1,000 alerts/day -> 900+ false positives -> analyst burnout, regulatory risk from missed true positives

**After AI**: 1,000 alerts/day -> 200-400 false positives -> focused analyst attention on real threats

---

## The Opportunity

| Workstream | Key Metric | Expected Improvement |
|-----------|-----------|---------------------|
| KYC/KYB & Transaction Monitoring | False positives | 90%+ down to 20-40% |
| KYC/KYB & Transaction Monitoring | Processing time | -65% |
| SRE & AIOps | MTTR | -50-75% (phased) |
| SRE & AIOps | Alert noise | -60-80% |
| Code Generation & Delivery | Developer productivity | +30-55% |
| Code Generation & Delivery | Deployment frequency | +30-40% |

## Four Workstreams

### 1. KYC/KYB & Transaction Monitoring AI (Highest Priority)
**Quick win**: AWS Textract for document OCR + Bedrock for unstructured document analysis
**Core**: SageMaker custom models for fraud/AML scoring with SHAP explainability
**Advanced**: Graph Neural Networks on Neptune for network-based AML detection

Your in-house KYC system is the biggest opportunity — full control over architecture, no vendor constraints. ML augmentation can layer directly onto existing pipelines.

Key finding: Amazon Fraud Detector is no longer accepting new customers. SageMaker custom models are the recommended path.

### 2. SRE & AIOps (Quick Win Available)
**Quick win**: Enable Datadog Bits AI (already paying for Datadog — just activate AI features)
**Core**: Custom LangGraph incident agent for financial-services-specific triage
**Advanced**: Predictive alerting + AI-driven capacity planning

Since Datadog is already deployed, this is your fastest path to value. No procurement, no new vendor. PagerDuty can be added later for on-call management if needed.

### 3. Code Generation & Software Delivery
**Quick win**: GitHub Copilot Enterprise for all developers
**Core**: GitLab Duo AI features for CI/CD + Snyk for security scanning
**Advanced**: AI-powered deployment risk scoring integrated with ArgoCD

Stack-specific notes:
- **Rust**: Copilot has decent support; Cursor or Claude Code supplement for complex Rust
- **Go**: Strong Copilot support, Amazon Q Developer good for AWS Go SDKs
- **Node.js**: Excellent coverage across all AI code gen tools
- **GitLab CI**: GitLab Duo provides native AI features (code suggestions, MR summaries, CI troubleshooting)
- **ArgoCD**: AI-assisted deployment validation and rollback decisions

Conservative ROI: 3.3x; Moderate: 6.9x; Optimistic: 9.7x (for 30-40 developers).

### 4. Compliance & Governance Framework
**Foundation**: SOC 2 + ISO 27001 control mapping for AI systems
**Financial regulation**: SR 11-7 model risk management (mandatory under OCC/Fed examination)
**Certification path**: ISO 42001 (AI management system) within 12-18 months

HIPAA is **not in scope** — your transaction data has no health data linkage. This simplifies vendor selection and reduces compliance overhead significantly.

Key finding: No single framework covers everything. Must layer: SOC 2/ISO 27001 (base) + NIST AI RMF + SR 11-7 + ISO 42001.

## Consolidated Budget Estimate (Refined)

| Category | Monthly | Annual |
|----------|---------|--------|
| KYC/KYB & Transaction AI (AWS services) | $30K-60K | $360K-720K |
| SRE & AIOps (Datadog AI add-on + custom) | $3K-12K | $36K-144K |
| Code generation tools (30-40 devs) | $3K-6K | $36K-72K |
| Compliance (GRC, audits, certification) | $18K-45K | $216K-540K |
| **Total (progressive adoption)** | **$54K-123K** | **$648K-1.48M** |

Note: SRE costs reduced because Datadog is already deployed. HIPAA removal saves ~$50-100K in compliance costs. Ranges reflect phased adoption — start with quick wins at ~$20K/mo.

## Recommended Vendor Stack (Consolidated)

| Category | Primary Vendor | Why |
|----------|---------------|-----|
| AI/ML Platform | AWS Bedrock + SageMaker | Compliance umbrella (SOC 2, PrivateLink), OCC-ready |
| LLM Provider | Claude via Bedrock | Best reasoning for document analysis, stays in AWS |
| Graph Database | Amazon Neptune | GNN for AML, ownership graphs, SOC 2 compliant |
| Code Generation | GitHub Copilot Enterprise | Market leader, IP indemnity, works with Rust/Go/Node |
| CI/CD AI | GitLab Duo | Native integration with your existing GitLab CI |
| Deployment | ArgoCD (existing) | Add AI-assisted rollback and validation |
| Observability + AIOps | Datadog (existing) | Enable Bits AI — no new vendor needed |
| Security Scanning | Snyk + Checkov | Code + IaC coverage |

**Principle**: Route all customer data AI workloads through AWS Bedrock (single compliance umbrella with PrivateLink, CloudTrail, KMS). Lean on existing tools (Datadog, GitLab, ArgoCD) before adding new ones.

## Phased Roadmap

```
Phase 1: Foundation (Months 1-3) — ~$20K/mo
├── Enable Datadog Bits AI (immediate — no procurement needed)
├── Deploy GitHub Copilot Enterprise to pilot team (10 devs)
├── Set up AWS Textract pipeline for KYC document OCR
├── Establish AI governance committee + SR 11-7 framework
├── Baseline all metrics (DORA, MTTR, false positive rates)
├── Begin ML experimentation on AML false positive reduction
└── Expected: 20-30% productivity gains, 25% MTTR reduction

Phase 2: Core Adoption (Months 3-6) — ~$55K/mo
├── SageMaker custom models for fraud/AML scoring
├── Bedrock Claude for document analysis and summarization
├── Expand Copilot to all developers
├── GitLab Duo AI features for CI/CD
├── Snyk security scanning in GitLab pipelines
├── First model validation under SR 11-7
└── Expected: 50% MTTR reduction, 60% false positive reduction

Phase 3: Advanced (Months 6-12) — ~$90K/mo
├── Neptune GNN for network-based AML detection
├── Entity resolution + beneficial ownership graphs
├── Custom LangGraph incident agent
├── AI-powered ArgoCD deployment validation
├── ISO 42001 certification preparation
└── Expected: 80% false positive reduction, 65% MTTR reduction

Phase 4: Scale & Optimize (Months 12-18) — ~$120K/mo
├── Expand AI models across all business lines
├── Predictive alerting and capacity planning
├── Full DORA metrics automation
├── Complete ISO 42001 certification
├── Publish case studies and ROI report
└── Expected: Full metrics realization across all workstreams
```

## Critical Compliance Requirements

1. **SR 11-7 model governance** is mandatory under OCC/Fed examination for all AI models making regulated decisions (KYC scoring, AML alerts, fraud detection)
2. **Human-in-the-loop** required for high-risk decisions (SAR filing, account blocking, production changes)
3. **Explainability** via SHAP/LIME is a cross-regulatory requirement for financial services AI
4. **Audit trails** for all AI decisions via CloudTrail + immutable logging
5. **Independent model validation** required — budget for third-party validator or hire internal analyst

## Key Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Model hallucination in KYC/AML | Medium | High | Human review for all high-risk decisions |
| Adversarial attacks on fraud models | Medium | High | Adversarial training, input validation, model monitoring |
| Labeled data scarcity for ML | High | Medium | Semi-supervised learning, active learning, SMOTE |
| Small team capacity for ML | High | Medium | Lean on Bedrock managed models, hire 1-2 ML engineers |
| Regulatory scrutiny of AI decisions | Medium | High | SR 11-7 framework, explainability, audit trails |
| Organizational resistance to AI | Medium | Medium | Champions program, phased rollout, training |

## Remaining Questions

1. **Data residency**: Any restrictions on where data can be processed (US-only, specific AWS regions)?
2. **Budget approval**: Is the $648K-1.48M/year range within expected investment levels?
3. **ML hiring**: Is there budget for 1-2 ML engineers, or should we rely fully on managed services?
4. **Existing AML rules**: How many rules are in the current rule-based AML system? (Affects hybrid model design)
5. **ArgoCD version**: Are you on Argo CD 2.x with ApplicationSets? (Affects AI integration approach)

## Next Steps

1. Run team readiness assessment using `templates/assessment-checklist.md`
2. Enable Datadog Bits AI (Day 1 quick win)
3. Start GitHub Copilot pilot with 10 developers
4. Begin AML false positive analysis — baseline current rules, identify ML augmentation points
5. Establish AI governance committee with SR 11-7 as the anchor framework
6. Hire or contract 1-2 ML engineers for SageMaker work

---

*Full research available in `research/sections/` | Comparison matrices in `research/comparisons/` | Reviews in `research/reviews/`*
