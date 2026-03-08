# Code Generation Tools — Comparison Matrix

**Research Date**: March 7, 2026 (Revised March 7, 2026)
**Context**: Financial services organization (SOC 2, ISO 27001, HIPAA), AWS-primary

> **Pricing Disclaimer**: All pricing figures are approximate and subject to change. Verify current pricing directly with vendors before procurement.

---

## Feature Comparison

| Feature | GitHub Copilot Enterprise | Amazon Q Developer Pro | Cursor Business | Claude Code | Cody Enterprise |
|---------|--------------------------|----------------------|-----------------|-------------|-----------------|
| **Code Completion** | Yes (all major langs) | Yes (15+ langs) | Yes (all major langs) | No (agentic, not autocomplete) | Yes (all major langs) |
| **Chat Interface** | IDE + GitHub.com | IDE + CLI | IDE-native | CLI-native | IDE |
| **Agentic Coding** | Copilot Workspace | /dev agent | Composer (multi-file) | Full agentic execution | Limited |
| **Multi-file Editing** | Via Workspace | Via /dev | Native (Composer) | Native | Limited |
| **Codebase Indexing** | Knowledge Bases | Limited | Full repo indexing | Git-aware context | Full code graph |
| **Security Scanning** | Via GitHub Advanced Security | Built-in SAST | No | Via hooks/tools | No |
| **Code Review AI** | PR summaries + review | /review agent | No | Headless CI mode | No |
| **Test Generation** | Inline suggestions | /test agent | Inline suggestions | Agentic test writing | Inline suggestions |
| **Custom Instructions** | Organization policies | Limited | .cursorrules files | CLAUDE.md + hooks | Custom commands |
| **IDE Support** | VS Code, JetBrains, Neovim, Xcode | VS Code, JetBrains | VS Code (fork) | Terminal (any) | VS Code, JetBrains |

---

## Security & Compliance Comparison

| Security Feature | GitHub Copilot Enterprise | Amazon Q Developer Pro | Cursor Business | Claude Code | Cody Enterprise |
|-----------------|--------------------------|----------------------|-----------------|-------------|-----------------|
| **SOC 2** | Type I certified (June 2024). Type II expected — verify current status with GitHub before procurement. | Yes, Type II (AWS) | Yes, Type II | Yes, Type II (Anthropic API). Claude Code itself does not have separate certification. | Yes, Type II |
| **HIPAA BAA** | GitHub Enterprise Cloud BAA exists; confirm Copilot-specific coverage with GitHub | Yes (AWS BAA) | No | No (use Claude via AWS Bedrock for HIPAA workloads) | Self-hosted possible |
| **Code Training Opt-out** | Yes (Business/Enterprise) | Yes (Professional) | Yes (Privacy Mode) | Yes (API) | Yes |
| **IP Indemnity** | Yes (Enterprise) | Limited | No | No | No |
| **Self-hosted Option** | No | No | No | Local execution | Yes |
| **SSO/SCIM** | Yes | Yes (AWS IAM) | Yes (Business) | N/A | Yes |
| **Audit Logs** | Yes (API) | Yes (CloudTrail) | Limited | Local logs only | Yes |
| **Content Exclusion** | Yes | Limited | N/A | Via CLAUDE.md | Repo permissions |
| **Code Referencing** | Yes (license detection) | No | No | No | No |
| **Data Residency** | US/EU options | AWS regions | Cursor servers | Local + API | Self-hosted |

---

## Pricing Comparison (March 2026)

| Plan | GitHub Copilot | Amazon Q Developer | Cursor | Claude Code | Cody |
|------|---------------|-------------------|--------|-------------|------|
| **Free** | Limited (individuals) | 50 scans/mo, basic | 2000 completions/mo | N/A | Limited |
| **Individual/Pro** | $10/mo | N/A | $20/mo | $20/mo (Pro) or $100/mo (Max) | $9/mo |
| **Business** | $19/mo | $19/mo | $40/mo | API pricing | $19/mo |
| **Enterprise** | $39/mo | Part of AWS Enterprise | Custom | API pricing | Custom |
| **50-dev Monthly Cost** | $1,950 | $950 | $2,000 | Variable | $950 |
| **50-dev Annual Cost** | $23,400 | $11,400 | $24,000 | Variable | $11,400 |

---

## Use Case Fit for Financial Services

| Use Case | Best Tool | Runner-up | Notes |
|----------|-----------|-----------|-------|
| **Daily coding assistance** | GitHub Copilot Enterprise | Amazon Q Developer | Copilot has broader IDE support + audit trail |
| **AWS infrastructure code** | Amazon Q Developer | GitHub Copilot | Q Developer has native AWS API knowledge |
| **Large codebase refactoring** | Cursor / Claude Code | Cody | Full repo context is critical. **Restrict to non-sensitive code** (see usage policy below) |
| **Security-first development** | Amazon Q Developer | GitHub Copilot + GHSA | Q has built-in SAST scanning |
| **Compliance audit trail** | GitHub Copilot Enterprise | Amazon Q (CloudTrail) | Copilot has dedicated audit log API |
| **On-premise / air-gapped** | Cody (self-hosted) | Claude Code (local) | Only options for full data control |
| **CI/CD integration** | Claude Code (headless) | Amazon Q CLI | Both support pipeline integration |
| **New developer onboarding** | Cody (code graph) | Cursor (codebase chat) | Understanding existing code is key |
| **Multi-repo context** | Cody | GitHub Copilot (Knowledge Bases) | Cody's code graph spans repos natively |
| **KYC/KYB domain code** | GitHub Copilot Enterprise | Amazon Q Developer | Use approved tools only for compliance-sensitive code |

---

## Usage Policy Restrictions for Financial Services

| Tool | Approved For | NOT Approved For |
|------|-------------|-----------------|
| **GitHub Copilot Enterprise** | All code (general use, compliance code, infrastructure) | Verify HIPAA-specific coverage before using on PHI-handling code |
| **Amazon Q Developer Pro** | All code including PHI-adjacent code (covered under AWS BAA) | — |
| **Cody Enterprise (self-hosted)** | All code (data stays on-premise) | Cloud-hosted Cody: same restrictions as Cursor |
| **Cursor Business** | Internal tooling, developer utilities, non-sensitive application code | Code handling customer PII/PHI, payment processing, compliance workflows |
| **Claude Code (direct API)** | Internal tooling, infrastructure code, developer utilities, non-sensitive code | Code handling customer PII/PHI, compliance-critical workflows |
| **Claude via AWS Bedrock** | All code including PHI-adjacent (covered under AWS BAA) | — |

---

## Decision Matrix: Weighted Scoring

Weights reflect financial services priorities (security and compliance weighted highest).

| Criterion (Weight) | GitHub Copilot Enterprise | Amazon Q Pro | Cursor Business | Claude Code | Cody Enterprise |
|--------------------|:-:|:-:|:-:|:-:|:-:|
| **Security & Compliance (25%)** | 8 | 9 | 6 | 7 | 8 |
| **Code Quality (20%)** | 8 | 7 | 9 | 9 | 8 |
| **IDE Integration (15%)** | 9 | 7 | 8 | 5 | 7 |
| **Enterprise Features (15%)** | 9 | 8 | 6 | 5 | 8 |
| **Financial Domain Fit (10%)** | 7 | 8 | 8 | 8 | 7 |
| **Cost Efficiency (10%)** | 7 | 9 | 7 | 6 | 9 |
| **Innovation/Agentic (5%)** | 8 | 7 | 9 | 10 | 6 |
| **Weighted Score** | **8.00** | **7.90** | **7.35** | **6.95** | **7.65** |

> Note: GitHub Copilot Enterprise score reduced from 9 to 8 on Security & Compliance pending SOC 2 Type II verification (see compliance table above). Score should be updated to 9 once Type II is confirmed, which would raise the weighted score to 8.25.

---

## Recommendation

### Primary: GitHub Copilot Enterprise
- Best overall fit for regulated financial services
- Strongest audit trail and compliance features
- Broadest IDE support minimizes adoption friction
- IP indemnity provides legal protection
- PR review integration completes the development workflow
- **Action**: Verify SOC 2 Type II status with GitHub sales before finalizing procurement

### Secondary: Amazon Q Developer Professional
- Complement for AWS-specific infrastructure work
- Built-in security scanning adds defense layer
- HIPAA BAA coverage under AWS agreement — approved for PHI-adjacent code
- Code transformation agent valuable for legacy modernization

### Specialist: Cody Enterprise (Self-Hosted)
- For teams/repos with strictest data sovereignty requirements
- Self-hosted deployment keeps all code on-premise
- Code graph provides superior codebase understanding

### For Agentic/Complex Tasks: Claude Code or Cursor (Restricted Use)
- Large refactoring projects and multi-file changes on non-sensitive code only
- Architecture exploration and documentation generation
- NOT approved for code handling customer PII, PHI, or compliance-critical workflows
- For PHI workloads requiring agentic capabilities, use Claude via AWS Bedrock

---

**Document Version**: 1.1 (Revised)
**Last Updated**: March 7, 2026
**Revision Notes**: Updated GitHub Copilot SOC 2 status with verification action item, added usage policy restrictions table, added pricing disclaimer, standardized "SOC 2" formatting, added monthly cost row, adjusted weighted score pending SOC 2 Type II verification.
