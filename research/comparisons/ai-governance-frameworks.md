# AI Governance Frameworks Comparison for Financial Services

**Research Date**: March 7, 2026
**Purpose**: Compare applicable AI governance frameworks and recommend a unified governance approach for a financial services organization

---

## Framework Overview

| Framework | Issuer | Type | Scope | Status |
|-----------|--------|------|-------|--------|
| **NIST AI RMF 1.0** | NIST (US) | Voluntary framework | All AI systems | Published Jan 2023, profiles ongoing |
| **FS AI RMF** | US Treasury | Sector-specific framework | Financial services AI | Published 2025 |
| **SR 11-7** | Fed/OCC | Regulatory guidance | Bank models (including AI/ML) | Published 2011, applied to AI |
| **ISO/IEC 42001** | ISO | International standard | AI management systems | Published Dec 2023 |
| **ISO 27001:2022** | ISO | International standard | Information security | Published Oct 2022 |
| **EU AI Act** | European Commission | Regulation (law) | AI systems in EU market | Phased: 2025-2027 |
| **SOC 2 TSC** | AICPA | Audit standard | Service organizations | Continuously updated |
| **HIPAA Security Rule** | HHS/OCR | Regulation (law) | PHI processing systems | 2025 proposed update |
| **CSA AI Controls Matrix** | Cloud Security Alliance | Industry guidance | Cloud AI systems | Published 2024 |

---

## Detailed Framework Comparison

### 1. NIST AI Risk Management Framework (AI RMF 1.0)

**Applicability**: Voluntary but increasingly referenced by US regulators. The Treasury FS AI RMF directly maps to NIST AI RMF.

**Core Functions**:

| Function | Purpose | Key Activities |
|----------|---------|---------------|
| **GOVERN** | Culture and accountability | Establish AI governance policies, assign accountability, define risk appetite |
| **MAP** | Context and risk identification | Categorize AI use cases, identify stakeholders, map risks, define success criteria |
| **MEASURE** | Risk assessment | Quantify risks (bias, accuracy, security), benchmark against thresholds |
| **MANAGE** | Risk treatment | Implement controls, monitor, respond to incidents, improve continuously |

**Financial Services Relevance**:
- Treasury's FS AI RMF maps NIST functions to **230 control objectives** specific to financial services
- Regulators (OCC, Fed, CFPB, SEC) increasingly reference NIST AI RMF principles
- Provides common language for discussing AI risk across regulatory examinations

**Strengths**: Comprehensive, flexible, US-government-endorsed, free
**Weaknesses**: Voluntary (no enforcement), high-level (requires interpretation), no certification

### 2. US Treasury Financial Services AI Risk Management Framework (FS AI RMF)

**Applicability**: Directly relevant to financial institutions. Published 2025.

**Key Components**:
- **AI Lexicon**: Standardized definitions for AI concepts in financial services
- **Risk and Control Matrix**: 230 mapped control objectives organized by NIST AI RMF functions
- **Implementation Guidance**: Practical guidance for operationalizing AI risk controls

**Control Objective Categories** (mapped to NIST functions):

| NIST Function | FS AI RMF Control Areas | Example Controls |
|---------------|------------------------|------------------|
| GOVERN | AI governance structure, policies, accountability | Board oversight of AI risk, AI risk appetite statement |
| MAP | Use-case classification, risk identification | AI inventory, risk tiering, stakeholder impact analysis |
| MEASURE | Performance metrics, bias testing, validation | Model accuracy monitoring, fairness metrics, stress testing |
| MANAGE | Incident response, change management, vendor management | AI incident playbook, model change approval, vendor due diligence |

**Strengths**: Financial-services-specific, maps to existing regulatory expectations, actionable controls
**Weaknesses**: New framework (limited audit experience), 230 controls may be overwhelming for initial adoption
**Source Note**: The FS AI RMF was announced via Treasury press release. The 230 control objectives are documented in the Risk and Control Matrix accompanying the framework. See [Lowenstein Sandler analysis](https://www.lowenstein.com/news-insights/publications/client-alerts/financial-services-ai-risk-management-framework-operationalizing-the-230-control-objectives-before-the-market-wakes-up-data-privacy) for detailed control objective breakdown

### 3. SR 11-7 / OCC 2011-12 (Model Risk Management)

**Applicability**: Mandatory for banks and financial institutions supervised by Fed/OCC. Strongly recommended for all financial services firms.

**Three Pillars**:

| Pillar | Requirement | AI/ML Implementation |
|--------|-------------|---------------------|
| **Model Development** | Sound design, documented assumptions | Algorithm selection rationale, training data documentation, feature justification |
| **Model Validation** | Independent testing | Holdout testing, adversarial testing, bias analysis, challenger models, explainability |
| **Ongoing Monitoring** | Performance tracking | Continuous drift detection, automated degradation alerts, retraining triggers |

**AI-Specific Extensions** (regulatory expectations evolving):
- **Explainability**: Models must be understandable to validators and examiners. Black-box models require SHAP/LIME explanations
- **Vendor Models**: Third-party AI (e.g., Bedrock foundation models) subject to same validation requirements
- **Non-Determinism**: Validation methodology must account for variability in AI outputs
- **Model Inventory**: All AI/ML models tracked with risk classification, validation status, and owner

**Strengths**: Established regulatory expectation, well-understood by examiners, proven framework
**Weaknesses**: Written pre-AI era (2011), requires interpretation for modern AI/ML, evolving expectations

### 4. ISO/IEC 42001:2023 (AI Management Systems)

**Applicability**: Voluntary international standard. Becoming enterprise-expected by 2026.

**Key Requirements**:

| Clause | Requirement | Implementation |
|--------|-------------|----------------|
| 4 | Context of the organization | Understand AI stakeholders, scope of AIMS |
| 5 | Leadership | Management commitment to responsible AI |
| 6 | Planning | AI risk assessment, objectives, treatment plans |
| 7 | Support | Resources, competence, awareness, communication |
| 8 | Operation | AI system lifecycle management, impact assessments |
| 9 | Performance evaluation | Monitoring, measurement, internal audit, management review |
| 10 | Improvement | Nonconformity, corrective action, continual improvement |

**Annex A Controls (AI-Specific)**:
- A.2: AI policy development
- A.3: Internal AI stakeholder engagement
- A.4: AI resources and competence
- A.5: AI system impact assessment
- A.6: AI system lifecycle management
- A.7: Data for AI systems (quality, bias, provenance)
- A.8: Transparency and explainability
- A.9: AI system accountability
- A.10: Third-party and vendor AI management

**Certification Path**: 6-12 months from preparation through certification. Organizations already ISO 27001 certified can achieve ISO 42001 up to 40% faster.

**Industry Adoption** (as of early 2026):
- AWS, Google Cloud, Microsoft Azure: Certified
- KPMG (US): Certified November 2025
- Multiple financial institutions pursuing certification

**Strengths**: First international AI-specific management system standard, certifiable, complements ISO 27001
**Weaknesses**: New (limited auditor experience), certification cost, not yet widely required by regulators

### 5. EU AI Act

**Applicability**: Mandatory if operating in EU, offering services to EU residents, or processing EU citizen data.

**Risk Classification**:

| Risk Level | Examples in Financial Services | Obligations | Maximum Penalty |
|------------|-------------------------------|-------------|-----------------|
| **Unacceptable** | Social scoring, exploitative AI | Prohibited | 35M EUR or 7% global turnover |
| **High-Risk** | Credit scoring, insurance risk assessment | Full compliance: risk management, data governance, documentation, human oversight, accuracy, robustness | 15M EUR or 3% global turnover |
| **Limited Risk** | Chatbots, emotion recognition | Transparency obligations | 7.5M EUR or 1.5% global turnover |
| **Minimal Risk** | Spam filters, code generation | No specific obligations | N/A |

**Notable**: Transaction monitoring for fraud detection is **explicitly excluded** from high-risk classification.

**Key Obligations for High-Risk AI**:
- Risk management system throughout lifecycle
- Quality management system
- Training data governance (quality, bias, representativeness)
- Technical documentation
- Record-keeping and traceability
- Transparency and information to deployers
- Human oversight capabilities
- Accuracy, robustness, and cybersecurity
- Conformity assessment (CE marking)
- Post-market monitoring

**Timeline**:
- Feb 2, 2025: Prohibited practices and AI literacy
- Aug 2, 2025: GPAI model obligations
- Aug 2, 2026: Full high-risk obligations
- Aug 2, 2027: High-risk AI in regulated products

**Strengths**: Legally binding, comprehensive, risk-based approach
**Weaknesses**: Complex, significant compliance burden, extraterritorial scope unclear

### 6. CSA AI Controls Matrix

**Applicability**: Voluntary industry guidance for cloud AI systems.

**Control Domains**:
- AI Governance and Accountability
- AI Data Management
- AI Model Development and Deployment
- AI Security and Privacy
- AI Transparency and Explainability
- AI Monitoring and Operations
- AI Incident Management

**Strengths**: Practical, cloud-focused, maps to other frameworks
**Weaknesses**: Not certifiable, less regulatory weight

---

## Framework Mapping: Control Crosswalk

This table maps common AI compliance requirements across frameworks to identify overlaps and gaps.

| Requirement | SOC 2 TSC | ISO 27001 | ISO 42001 | SR 11-7 | NIST AI RMF | EU AI Act | HIPAA |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Access Controls** | CC6 | A.8.3-5 | -- | -- | GOVERN | Art. 15 | 164.312(a) |
| **Encryption** | CC6 | A.8.24 | -- | -- | MANAGE | Art. 15 | 164.312(a)(2)(iv) |
| **Audit Logging** | CC7 | A.8.15-16 | -- | Monitoring | MANAGE | Art. 12 | 164.312(b) |
| **Change Management** | CC8 | A.8.32 | A.6 | Development | MANAGE | Art. 9 | 164.312(e) |
| **Risk Assessment** | CC9 | A.5.12 | Clause 6 | All pillars | MAP | Art. 9 | 164.308(a)(1) |
| **AI Model Validation** | PI1 | A.8.25 | A.6 | Validation | MEASURE | Art. 10 | -- |
| **Bias Testing** | -- | -- | A.7-8 | Validation | MEASURE | Art. 10 | -- |
| **Explainability** | -- | -- | A.8 | Validation | MAP | Art. 13 | -- |
| **Data Quality** | PI1 | A.8.10 | A.7 | Development | MAP | Art. 10 | -- |
| **Human Oversight** | -- | -- | A.8 | Governance | GOVERN | Art. 14 | -- |
| **Vendor Management** | CC9 | A.5.19-22 | A.10 | Vendor models | GOVERN | Art. 28 | 164.308(b) |
| **Incident Response** | CC7 | A.5.24-28 | Clause 10 | Monitoring | MANAGE | Art. 62 | 164.308(a)(6) |
| **Data Minimization** | C1 | A.8.10-11 | A.7 | -- | MAP | Art. 10 | 164.502(b) |
| **Availability/Failover** | A1 | A.8.14 | -- | -- | MANAGE | Art. 15 | 164.308(a)(7) |
| **Model Inventory** | -- | A.8.1 | A.6 | Inventory | MAP | Art. 49 | -- |
| **Training Data Governance** | C1 | A.8.10 | A.7 | Development | MAP | Art. 10 | 164.530 |

**Key Gaps Identified**:
- SOC 2 and ISO 27001 have **no native controls** for AI bias, explainability, or human oversight — these require ISO 42001 or NIST AI RMF supplementation
- HIPAA has **no AI-specific provisions** (the 2025 proposed update begins addressing this)
- SR 11-7 is strong on validation but **weak on ethics/fairness** — supplement with NIST AI RMF or ISO 42001

---

## Recommended Governance Stack

### Primary Framework Selection

For a US financial services organization with SOC 2, ISO 27001, and HIPAA:

```
Layer 1 (Foundation):     SOC 2 + ISO 27001 + HIPAA
                          [Existing compliance — extend to cover AI systems]

Layer 2 (AI Governance):  NIST AI RMF / FS AI RMF
                          [AI-specific risk management mapped to 230 controls]

Layer 3 (Financial Reg):  SR 11-7 Model Risk Management
                          [Mandatory for regulated model decisions]

Layer 4 (Certification):  ISO 42001 (target Year 2)
                          [International AI management certification]

Layer 5 (If EU scope):    EU AI Act compliance
                          [Only if processing EU citizen data or operating in EU]
```

### Implementation Priority

| Priority | Framework | Timeline | Effort |
|----------|-----------|----------|--------|
| **P0 - Immediate** | Extend SOC 2/ISO 27001/HIPAA controls to AI systems | Months 1-3 | Medium |
| **P0 - Immediate** | SR 11-7 compliance for AI models in regulated decisions | Months 1-3 | High |
| **P1 - Near-term** | NIST AI RMF / FS AI RMF adoption | Months 3-6 | High |
| **P2 - Medium-term** | ISO 42001 certification preparation | Months 6-12 | Medium |
| **P3 - If applicable** | EU AI Act compliance assessment | Months 6-12 | Medium-High |

### Governance Structure

```
Board of Directors
    |
    v
AI Governance Committee
(meets quarterly; includes CRO, CISO, CLO, CTO, business heads)
    |
    +-- AI Policy & Standards (CISO / Compliance)
    |       - AI Acceptable Use Policy
    |       - AI Vendor Approval Process
    |       - AI Data Classification Standards
    |
    +-- Model Risk Management (CRO / Risk)
    |       - Model Inventory & Tiering
    |       - Independent Validation
    |       - Ongoing Monitoring
    |
    +-- AI Ethics & Fairness (CLO / Compliance)
    |       - Bias Testing Requirements
    |       - Explainability Standards
    |       - Customer Impact Assessment
    |
    +-- AI Operations (CTO / Engineering)
            - Model Development Standards
            - Deployment & Change Management
            - Security & Access Controls
```

### Policy Documents Required

| Policy | Primary Framework Reference | Status |
|--------|---------------------------|--------|
| AI Acceptable Use Policy | ISO 42001 A.2, NIST GOVERN | Must create |
| AI Risk Classification Methodology | FS AI RMF MAP, SR 11-7 | Must create |
| AI Model Development Standard | SR 11-7, ISO 42001 A.6 | Must create |
| AI Model Validation Procedure | SR 11-7, NIST MEASURE | Must create |
| AI Vendor Assessment Procedure | SOC 2 CC9, ISO 27001 A.5.19 | Extend existing |
| AI Data Governance Policy | ISO 42001 A.7, NIST MAP | Must create |
| AI Incident Response Plan | SOC 2 CC7, ISO 27001 A.5.24 | Extend existing |
| AI Ethics and Bias Policy | ISO 42001 A.8, NIST MEASURE | Must create |
| AI Training Data Retention Policy | HIPAA, ISO 27001 A.8.10 | Must create |

---

## Annual Compliance Calendar

| Month | Activity | Framework |
|-------|----------|-----------|
| January | AI model inventory refresh | SR 11-7, ISO 42001 |
| February | Vendor compliance certification review | SOC 2, ISO 27001 |
| March | AI risk assessment update | NIST AI RMF, FS AI RMF |
| April | Bias testing for all production models | SR 11-7, NIST MEASURE |
| May | SOC 2 audit preparation (AI controls) | SOC 2 |
| June | ISO 27001 surveillance audit (AI scope) | ISO 27001 |
| July | AI governance committee annual review | All |
| August | Model validation cycle (high-tier models) | SR 11-7 |
| September | HIPAA risk assessment update (AI systems) | HIPAA |
| October | AI vendor re-assessment | SOC 2 CC9, ISO 27001 |
| November | Regulatory exam preparation | SR 11-7, BSA/AML |
| December | Annual AI governance report to board | All |

---

## References

### Frameworks and Standards
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [US Treasury FS AI RMF](https://home.treasury.gov/news/press-releases/sb0401)
- [FS AI RMF: Operationalizing 230 Control Objectives](https://www.mondaq.com/unitedstates/fintech/1751798/financial-services-ai-risk-management-framework-operationalizing-the-230-control-objectives-before-the-market-wakes-up)
- [Federal Reserve SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm)
- [ISO/IEC 42001:2023](https://www.iso.org/standard/42001)
- [EU AI Act](https://artificialintelligenceact.eu/high-level-summary/)
- [CSA AI Controls Matrix](https://cloudsecurityalliance.org/artifacts/ai-controls-matrix)

### Implementation Guidance
- [NIST AI RMF 2025 Updates](https://www.ispartnersllc.com/blog/nist-ai-rmf-2025-updates-what-you-need-to-know-about-the-latest-framework-changes/)
- [ISO 42001 Certification Steps (CSA)](https://cloudsecurityalliance.org/blog/2025/07/07/6-key-steps-to-iso-42001-certification-explained)
- [KPMG ISO 42001 Certification](https://kpmg.com/us/en/media/news/kpmg-receives-iso-ai-certification.html)
- [SR 11-7 Compliance Guide (ValidMind)](https://validmind.com/blog/sr-11-7-model-risk-management-compliance/)
- [Draft NIST Guidelines: Cybersecurity for AI Era](https://www.nist.gov/news-events/news/2025/12/draft-nist-guidelines-rethink-cybersecurity-ai-era)

### Financial Services Specific
- [EU AI Act Impact on Financial Services](https://www.consultancy.eu/news/11237/the-eu-ai-act-the-impact-on-financial-services-institutions)
- [AI in Banking: BPI Guidance](https://bpi.com/wp-content/uploads/2024/04/Navigating-Artificial-Intelligence-in-Banking.pdf)
- [AI Regulations: State and Federal Laws 2026](https://drata.com/blog/artificial-intelligence-regulations-state-and-federal-ai-laws-2026)

---

**Document Version**: 1.1 (revised per fact-check and peer review)
**Last Updated**: March 7, 2026 (revised)
**Next Review**: June 2026 (quarterly, or when new regulations issued)
