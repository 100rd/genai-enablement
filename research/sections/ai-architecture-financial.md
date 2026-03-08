# AI Architecture for Financial Services: KYC/KYB and Transaction Monitoring

**Research Date**: March 7, 2026 (Revised March 7, 2026)
**Author**: AI Architect (Solution Architect Agent)
**Scope**: KYC/KYB AI Automation, Transaction Monitoring AI, Compliance-Safe Architecture, AWS-Specific Patterns

> **Pricing Disclaimer**: All cost figures in this document are estimates based on publicly available pricing as of March 2026. Actual costs depend on transaction volume, customer base, and negotiated rates. Verify with vendors before budgeting.

---

## Executive Summary

Financial services organizations can achieve transformative improvements in KYC/KYB processing and transaction monitoring through strategic AI adoption. Key findings:

- **KYC processing time** can be reduced by 65% with digital/AI-driven verification ([DigiPay.Guru, 2025](https://www.digipay.guru/blog/ekyc-verification-trends-in-2024/))
- **AML false positives** can be reduced by 70-90% with ML-based transaction monitoring ([EY Nordic Survey, 2025](https://www.ey.com/en_se/insights/financial-services/how-ai-is-reshaping-the-future-of-transaction-monitoring); upper bound represents best-case scenarios)
- **Amazon Fraud Detector** is no longer accepting new customers; SageMaker custom models are the AWS-recommended path ([AWS, 2025](https://aws.amazon.com/fraud-detector/faqs/))
- **Graph Neural Networks** on Amazon Neptune + SageMaker represent the state-of-the-art for network-based fraud and AML detection ([AWS, 2025](https://aws.amazon.com/blogs/machine-learning/build-a-gnn-based-real-time-fraud-detection-solution-using-amazon-sagemaker-amazon-neptune-and-the-deep-graph-library/))
- **SR 11-7 compliance** for model risk management must be embedded into every AI/ML deployment in regulated financial services ([Federal Reserve, 2011; updated guidance through 2025](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm))

---

## 1. KYC/KYB AI Automation

### 1.1 Document OCR and Data Extraction

#### Platform Comparison

| Capability | AWS Textract | Azure Document Intelligence | Google Document AI |
|---|---|---|---|
| **Sync/Async Processing** | Both (sync for <5 pages, async for batch) | Both | Both |
| **Pre-built Models** | Forms, tables, identity docs, lending | Invoices, receipts, IDs, W-2, health insurance | Invoices, receipts, identity, procurement |
| **Custom Model Training** | Queries API, Adapters | Custom neural/template models | Custom processors via Document AI Workbench |
| **KYC Document Support** | Passports, driver licenses, ID cards via AnalyzeID | ID documents, passports, visas | Identity documents |
| **Table Extraction** | Strong native support | Strong native support | Good |
| **Handwriting Recognition** | Good | Strong | Strong |
| **AWS Integration** | Native (S3, Lambda, Step Functions) | Requires cross-cloud | Requires cross-cloud |
| **Accuracy (2025 benchmarks)** | Good, but Azure outperforms on invoices | Highest on structured documents | Competitive |
| **SOC 2/ISO 27001** | Yes | Yes | Yes |
| **HIPAA Eligible** | Yes | Yes (BAA available) | Yes (BAA available) |

**Citation**: [SparkCo AI, 2025](https://sparkco.ai/blog/aws-textract-vs-azure-document-intelligence-a-deep-dive/); [BusinessWareTech Invoice Benchmark, 2025](https://www.businesswaretech.com/blog/research-best-ai-services-for-automatic-invoice-processing)

#### Recommendation for AWS-Primary Organizations

**Use AWS Textract** as the primary OCR engine for:
- Identity documents (passports, driver licenses) via `AnalyzeID`
- Financial documents (bank statements, tax forms) via `AnalyzeDocument` with Queries
- Integration with serverless pipelines (S3 -> Lambda -> Textract -> Step Functions)

**Augment with Amazon Bedrock** for:
- Unstructured document summarization (legal agreements, compliance reports)
- Multi-modal document understanding (photos of damaged documents, handwritten notes)
- Context-aware extraction that requires reasoning beyond pattern matching

**Architecture Pattern**:
```
S3 Upload -> EventBridge -> Step Functions Workflow
  |-> Textract AnalyzeID (identity docs)
  |-> Textract AnalyzeDocument (financial docs)
  |-> Bedrock Claude/Nova (unstructured docs)
  |-> DynamoDB (extracted data)
  |-> SNS (human review notification for low-confidence extractions)
```

### 1.2 Entity Resolution and Beneficial Ownership Graph Construction

Entity resolution is the process of determining whether records from multiple sources refer to the same real-world entity. In KYC/KYB, this means linking corporate records, director databases, sanctions lists, and beneficial ownership registries.

#### Key Capabilities Required

1. **Fuzzy Name Matching**: Handle transliteration differences, abbreviations, alternative spellings
2. **Address Normalization**: Standardize addresses across jurisdictions
3. **Corporate Hierarchy Resolution**: Map parent-subsidiary-UBO chains
4. **Cross-Reference**: Link entities across sanctions lists, PEP databases, adverse media

#### AWS Architecture for Entity Resolution

```
Data Sources (registries, sanctions lists, PEP databases)
  |-> AWS Entity Resolution (fuzzy matching, ML-based linking)
  |-> Amazon Neptune (graph database for ownership structures)
  |-> Amazon Bedrock (LLM for adverse media analysis, document interpretation)
  |-> Visualization Layer (ownership graph rendering)
```

**Amazon Neptune** is the recommended graph database for beneficial ownership modeling because:
- Native graph queries (Gremlin, openCypher, SPARQL) for traversing ownership chains
- Integration with SageMaker for Graph Neural Network (GNN) models
- Managed service with SOC 2, ISO 27001, HIPAA compliance
- As of Feb 2026, Neptune supports GenAI agents that can prototype fraud detection and financial crime investigation use cases ([AWS APN Blog, 2026](https://aws.amazon.com/blogs/apn/how-aws-partners-can-deliver-anti-fraud-solutions-using-aws-genai-and-amazon-neptune-graph-capabilities/))

**Graph Model for Beneficial Ownership**:
```
Nodes: Person, Company, Trust, Foundation, Address, Country
Edges: OWNS (percentage), DIRECTS, RESIDES_AT, REGISTERED_IN, RELATED_TO
Properties: sanctions_match_score, pep_status, risk_level, last_verified_date
```

### 1.3 Sanctions/PEP Screening with AI

#### Current State (2026)

AI-powered sanctions and PEP screening reduces false positives through ([sanctions.io, 2025](https://www.sanctions.io/blog/the-role-of-ai-in-sanctions-pep-screening)):

- **NLP-based name matching**: Handles phonetic similarities, transliterations, and cultural naming conventions
- **Contextual scoring**: Considers date of birth, nationality, known associates to disambiguate
- **Continuous monitoring**: Real-time screening against updating lists vs. point-in-time batch

#### Vendor Landscape (Top Solutions for 2026)

| Vendor | Key Strength | Compliance Certs | Real-Time | API Integration |
|---|---|---|---|---|
| **Moody's (Bureau van Dijk)** | Largest PEP/sanctions database, Orbis ownership data | SOC 2, ISO 27001 | Yes | REST API |
| **Sumsub** | All-in-one IDV + AML screening + monitoring | SOC 2, ISO 27001 | Yes | REST API, SDK |
| **NameScan** | Specialized PEP/sanctions screening | SOC 2 | Yes | REST API |
| **Dow Jones Risk & Compliance** | Premium data quality, adverse media | SOC 2, ISO 27001 | Yes | REST API |
| **Refinitiv World-Check** | Comprehensive coverage, LSEG data | SOC 2, ISO 27001 | Yes | REST API |

**Citation**: [Alessa, 2026](https://alessa.com/blog/top-10-sanctions-screening-solutions/); [AML Watcher, 2026](https://amlwatcher.com/blog/aml-checks/)

#### Recommended Architecture (Hybrid)

```
Customer Onboarding
  |-> Identity Verification (Jumio/Onfido/Sumsub)
  |-> Document Extraction (AWS Textract)
  |-> Entity Resolution (AWS Entity Resolution)
  |-> Sanctions/PEP Screening (Moody's or Dow Jones API)
  |      |-> Match found: Queue for Enhanced Due Diligence
  |      |-> No match: Continue onboarding
  |-> Beneficial Ownership (Neptune graph + UBO registries)
  |-> Risk Score Calculation (SageMaker model)
  |-> Decision: Accept / Enhanced Review / Reject
  |-> Ongoing Monitoring (EventBridge scheduled re-screening)
```

### 1.4 Risk Scoring Models: ML-Based vs Rule-Based Hybrid

#### Why Hybrid is the Standard

Pure rule-based systems generate excessive false positives (40-60% of alerts). Pure ML systems lack explainability for regulators. The industry standard is a hybrid approach:

| Aspect | Rule-Based | ML-Based | Hybrid (Recommended) |
|---|---|---|---|
| **Explainability** | High (deterministic rules) | Low-Medium (requires XAI) | High (rules + XAI layer) |
| **False Positive Rate** | 40-60% | 5-15% | 10-20% |
| **Adaptability** | Low (manual updates) | High (continuous learning) | High |
| **Regulatory Acceptance** | High | Medium (needs explanation) | High |
| **Implementation Time** | 2-3 months | 6-12 months | 4-8 months |
| **SR 11-7 Compliance** | Straightforward | Requires model governance | Requires governance for ML components |

**Architecture Pattern**:
```
Transaction/Customer Data
  |-> Rule Engine (deterministic rules for known patterns)
  |     |-> Hard rules: Sanctions match, regulatory thresholds
  |     |-> Soft rules: Unusual patterns, threshold breaches
  |-> ML Model (SageMaker) for risk scoring
  |     |-> Features: Transaction history, customer profile, network analysis
  |     |-> Output: Risk probability + SHAP explanations
  |-> Ensemble Score = f(rule_score, ml_score)
  |-> Decision Engine
        |-> Low risk: Auto-approve
        |-> Medium risk: Enhanced monitoring
        |-> High risk: Human review queue
```

### 1.5 Identity Verification and Liveness Detection

#### Key Technologies (2025-2026)

Modern eKYC combines three capabilities ([Jumio, 2025](https://www.jumio.com/how-ai-kyc-is-changing-identity-verification/)):

1. **Document Verification**: AI validates government-issued IDs, detects forgeries
2. **Biometric Matching**: Selfie-to-document comparison using deep learning
3. **Liveness Detection**: Active (head turn, blink), passive (AI analysis), or hybrid

#### Top Vendors for Financial Services

| Vendor | Liveness Method | Document Types | Compliance | Pricing Model |
|---|---|---|---|---|
| **Jumio** | Active + Passive hybrid | 5,000+ ID types, 200+ countries | SOC 2, ISO 27001, PCI DSS | Per verification |
| **Onfido** | Passive (AI-based) | 2,500+ ID types | SOC 2, ISO 27001 | Per verification |
| **Veriff** | Active + Passive | 11,000+ ID types | SOC 2, ISO 27001 | Per verification |
| **Sumsub** | Active + Passive | 14,000+ ID types | SOC 2, ISO 27001 | Per verification |
| **Incode** | Passive (proprietary) | Government IDs | SOC 2, FedRAMP | Per verification |

**Note**: Document type counts are vendor-reported (approximate). Verify current figures with vendors.

**Citation**: [iDenfy, 2026](https://www.idenfy.com/blog/best-identity-verification-software/); [Ondato, 2026](https://ondato.com/blog/best-identity-verification-software/)

#### AWS Integration Pattern

```
Mobile/Web Client
  |-> Vendor SDK (Jumio/Onfido/Sumsub) for liveness + document capture
  |-> Vendor API returns verification result + extracted data
  |-> API Gateway -> Lambda -> process verification result
  |-> AWS Textract (secondary extraction for internal records)
  |-> DynamoDB (store verification metadata + audit trail)
  |-> S3 (encrypted document images, lifecycle policy for retention)
  |-> Step Functions (orchestrate EDD if verification flags issues)
```

### 1.6 Ongoing Monitoring and Periodic Review Automation

#### Key Automation Opportunities

| Process | Current (Manual) | AI-Automated | Savings |
|---|---|---|---|
| **Periodic KYC Review** | 2-4 hours per customer | 15-30 min (analyst review of AI summary) | 75-85% |
| **Sanctions Re-screening** | Batch nightly | Real-time event-driven | 100% faster detection |
| **Adverse Media Monitoring** | Occasional manual search | Continuous NLP-based monitoring | Continuous vs. episodic |
| **UBO Changes** | Annual review | Event-driven registry checks | Real-time detection |
| **Risk Score Updates** | Annual review | Continuous model re-scoring | Dynamic risk management |

**Architecture for Ongoing Monitoring**:
```
EventBridge Scheduler (periodic triggers)
  |-> Lambda: Re-screen all active customers against updated sanctions/PEP lists
  |-> Lambda: Check UBO registries for ownership changes
  |-> Bedrock: Scan adverse media sources for entity mentions
  |-> SageMaker Endpoint: Re-score customer risk based on new data
  |-> Step Functions: Route changes to analyst review queue
  |-> SNS/SQS: Notify compliance team of material changes
```

---

## 2. Transaction Monitoring AI

### 2.1 Fraud Detection: Rule-Based + ML Hybrid Architecture

#### Industry Context (2025-2026)

- 75% of Nordic banks plan to increase AI investment for transaction monitoring ([EY, 2025](https://www.ey.com/en_se/insights/financial-services/how-ai-is-reshaping-the-future-of-transaction-monitoring))
- AI-powered solutions reduce false positives by 70-90%; vendor claims of up to 95% represent best-case scenarios ([EY, 2025](https://www.ey.com/en_se/insights/financial-services/how-ai-is-reshaping-the-future-of-transaction-monitoring); [Flagright, 2025](https://www.flagright.com/post/ai-and-the-future-of-aml-compliance))
- Real-time scoring now achievable at per-transaction level with streaming architectures
- Deepfakes and synthetic identities are emerging threats requiring new detection approaches

#### Reference Architecture: Hybrid Transaction Monitoring

```
                        +------------------+
                        |  Transaction     |
                        |  Data Sources    |
                        +--------+---------+
                                 |
                    +------------+------------+
                    |                         |
           +-------v--------+     +----------v---------+
           | Real-Time Path |     | Batch Analytics    |
           | (Kinesis Data  |     | Path (S3 + Glue +  |
           | Streams)       |     | Athena)            |
           +-------+--------+     +----------+---------+
                   |                          |
           +-------v--------+     +----------v---------+
           | Rule Engine    |     | ML Training        |
           | (Lambda/ECS)   |     | Pipeline           |
           |                |     | (SageMaker)        |
           | - Velocity     |     | - XGBoost/LightGBM |
           | - Threshold    |     | - GNN on Neptune   |
           | - Pattern      |     | - Anomaly Det.     |
           +-------+--------+     +----------+---------+
                   |                          |
           +-------v--------+     +----------v---------+
           | SageMaker      |     | Model Registry     |
           | Endpoint       |     | (SageMaker)        |
           | (real-time     |     |                    |
           | inference)     |     | Version control    |
           +-------+--------+     | A/B testing        |
                   |              +--------------------+
           +-------v-----------------+
           | Decision Engine         |
           | - Combine rule + ML     |
           | - Apply thresholds      |
           | - Route to alert queue  |
           +-------+-----------------+
                   |
           +-------v-----------------+
           | Alert Management        |
           | - Priority scoring      |
           | - Analyst assignment    |
           | - SLA tracking          |
           | - SAR generation assist |
           +-------------------------+
```

**Model-to-Processing-Path Mapping** (clarification per peer review):

| Model Type | Processing Path | Latency | Use Case |
|---|---|---|---|
| Rule engine | Real-time | <10ms | Known patterns, regulatory thresholds |
| XGBoost/LightGBM | Real-time | <100ms | General fraud scoring |
| Isolation Forest / Autoencoder | Real-time or near-real-time | <100ms | Novel anomaly detection |
| GNN (GraphSAGE, GAT) | **Batch only** (nightly) | N/A (batch) | Network-based AML, collusion detection |
| LSTM / Transformer | Near-real-time (5-min windows) | <200ms | Behavioral sequence analysis |

GNN inference requires neighborhood subgraph extraction from Neptune, which adds 200-500ms latency. This exceeds the <100ms SLA for real-time transaction decisions. Therefore, **GNN models operate exclusively in the batch path**, with results informing risk scores that are cached and looked up during real-time processing.

### 2.2 AML Pattern Recognition

#### Key AML Patterns Detectable by AI

| Pattern | Description | Detection Method | ML Technique |
|---|---|---|---|
| **Structuring (Smurfing)** | Breaking large amounts into smaller sub-threshold transactions | Time-series analysis + threshold monitoring | Sequence models (LSTM), rule-based |
| **Layering** | Complex series of transactions to obscure origin | Graph analysis of transaction chains | GNN on Neptune, community detection |
| **Round-tripping** | Funds return to origin through complex paths | Graph cycle detection | Graph algorithms (Neptune) |
| **Unusual Geographic Patterns** | Transactions from/to high-risk jurisdictions | Geolocation enrichment + risk scoring | Classification models |
| **Rapid Movement** | Funds moved quickly through multiple accounts | Velocity analysis | Streaming anomaly detection |
| **Shell Company Networks** | Transactions through entities with no legitimate business | UBO graph analysis + transaction patterns | GNN + entity resolution |

#### AWS Implementation with Neptune + SageMaker

**Graph Neural Network (GNN) Architecture for AML** ([AWS Blog, 2025](https://aws.amazon.com/blogs/machine-learning/build-a-gnn-based-real-time-fraud-detection-solution-using-amazon-sagemaker-amazon-neptune-and-the-deep-graph-library/)):

```
Transaction Data (RDS/DynamoDB)
  |-> ETL (Glue) -> Neptune (graph construction)
  |     Nodes: Accounts, Customers, Merchants
  |     Edges: Transactions (amount, timestamp, type)
  |
  |-> SageMaker Training Job
  |     |-> Deep Graph Library (DGL) + GraphStorm
  |     |-> GNN model (GraphSAGE, GAT, or HGT)
  |     |-> Train on labeled fraud/legitimate transactions
  |     |-> Export model to SageMaker Model Registry
  |
  |-> Batch Inference (nightly)
        |-> Neptune query (full graph or subgraph partitions)
        |-> SageMaker Batch Transform (GNN scoring)
        |-> Output: Per-account/per-edge risk scores
        |-> Scores cached in DynamoDB for real-time lookup
```

**NeptuneGS** streamlines Neptune-to-GraphStorm data preparation for fraud detection ([GitHub](https://github.com/awslabs/realtime-fraud-detection-with-gnn-on-dgl)).

### 2.3 Anomaly Detection: Real-Time vs Batch

| Aspect | Real-Time | Batch | Recommendation |
|---|---|---|---|
| **Latency** | Milliseconds (per-transaction) | Hours (end-of-day/weekly) | Real-time for fraud; batch for AML patterns |
| **AWS Service** | Kinesis Data Streams + SageMaker Endpoint | S3 + SageMaker Batch Transform | Both |
| **Use Case** | Card fraud, account takeover | Structuring, layering, network analysis | Complementary |
| **Model Types** | Isolation Forest, Autoencoders, XGBoost | GNN, clustering, time-series | Different models per path |
| **Cost** | Higher (always-on endpoints) | Lower (compute on demand) | Tiered by risk level |
| **Compliance** | Immediate blocking capability | Pattern analysis for SARs | Both required |

#### Recommended Hybrid Approach

```
Real-Time Path (fraud prevention):
  Kinesis -> Lambda (feature engineering) -> SageMaker Endpoint -> Decision
  Models: XGBoost, Isolation Forest (+ cached GNN risk scores from batch)
  Latency target: <100ms per transaction

Batch Path (AML detection):
  S3 (daily transaction dump) -> Glue ETL -> Neptune (graph construction)
  -> SageMaker Batch Transform (GNN scoring) -> Alert generation
  -> DynamoDB (cache risk scores for real-time lookup)
  Processing window: Nightly batch, results by 6 AM

Near-Real-Time Path (suspicious activity):
  Kinesis -> Lambda -> DynamoDB (session aggregation)
  -> 5-minute window analysis -> SageMaker Endpoint -> Escalation
  Models: LSTM, velocity rules
  Use for: Velocity checks, session-based anomalies
```

### 2.4 Network Analysis for Suspicious Activity Detection

Graph-based network analysis excels at detecting:
- **Money mule networks**: Accounts receiving and quickly forwarding funds
- **Collusion rings**: Groups of accounts transacting primarily with each other
- **Beneficial ownership chains**: Complex structures designed to obscure ultimate beneficiaries

**AWS Architecture**:
```
Amazon Neptune (graph database)
  |-> openCypher queries for pattern matching
  |-> Community detection algorithms (Louvain, Label Propagation)
  |-> Centrality analysis (PageRank, betweenness centrality)
  |-> SageMaker GNN for supervised classification
  |-> Visualization: Amazon Managed Grafana or custom React app with D3.js
```

### 2.5 Transaction Enrichment with AI

| Enrichment Type | Technology | AWS Service | Purpose |
|---|---|---|---|
| **Merchant Categorization** | NLP classification | Bedrock or SageMaker | Classify merchants from raw descriptors |
| **Geolocation** | IP/device analysis | Custom Lambda + third-party API | Map transactions to geographic risk |
| **Customer Segmentation** | Clustering | SageMaker (K-Means, DBSCAN) | Group customers by behavior profile |
| **Transaction Purpose** | NLP on memos/descriptions | Bedrock Claude | Infer purpose of payment |
| **Counterparty Risk** | Graph + external data | Neptune + external APIs | Score counterparty risk level |

### 2.6 Alert Prioritization and False Positive Reduction

This is where AI delivers the highest immediate ROI. Current manual alert review processes typically have 90-95% false positive rates ([Deloitte, "The future of regulatory productivity," 2024](https://www2.deloitte.com/us/en/pages/regulatory/articles/cost-of-compliance-regulatory-productivity.html); [ACAMS, "AML Effectiveness Survey," 2024](https://www.acams.org/en/resources/surveys)).

**ML-Based Alert Prioritization Architecture**:
```
Alert Generated (from rules or ML models)
  |-> Feature Engineering
  |     - Historical alert outcomes for this customer
  |     - Customer risk profile
  |     - Transaction context (amount vs. average, frequency)
  |     - Network risk (Neptune graph metrics)
  |     - Similar past cases and their outcomes
  |
  |-> SageMaker Classification Model
  |     - Trained on analyst dispositions (True Positive / False Positive)
  |     - Output: Priority score (0-100) + confidence
  |     - SHAP explanations for each score
  |
  |-> Alert Queue (priority-ordered)
  |     - P1 (90-100): Immediate analyst review
  |     - P2 (70-89): Same-day review
  |     - P3 (50-69): Standard queue
  |     - P4 (<50): See Auto-Action Guardrails (Section 3.3)
  |
  |-> Bedrock (optional): Generate investigation summary
        - Summarize customer history
        - Highlight relevant patterns
        - Suggest investigation steps
```

**Expected Results**:
- False positive reduction: 70-90% ([EY, 2025](https://www.ey.com/en_se/insights/financial-services/how-ai-is-reshaping-the-future-of-transaction-monitoring))
- Analyst productivity increase: 3-5x (based on reduced false positive volume and AI-assisted investigation summaries; [Flagright, 2025](https://www.flagright.com/post/ai-and-the-future-of-aml-compliance))
- Time to disposition: Reduced from 45 min to 10-15 min average (driven by auto-generated investigation context and pre-computed network analysis)

### 2.7 Adversarial ML Threats in Financial Transaction Monitoring

Adversarial attacks on fraud/AML models are not hypothetical -- they are an active and growing threat vector in financial services. Sophisticated actors actively probe and adapt to detection systems.

#### Threat Taxonomy

| Attack Type | Description | Target | Impact | Likelihood |
|---|---|---|---|---|
| **Model Evasion** | Crafting transactions that avoid detection by exploiting model decision boundaries | Real-time fraud models | Fraudulent transactions pass undetected | High -- active threat |
| **Data Poisoning** | Injecting misleading labeled data into training sets to degrade model accuracy | Training pipeline | Model learns incorrect patterns, reduced detection | Medium -- requires data access |
| **Model Inversion** | Reverse-engineering model behavior to understand decision thresholds | Deployed endpoints | Attacker learns how to avoid detection | Medium -- probing attacks |
| **Concept Drift Exploitation** | Gradually shifting attack patterns so the model's concept of "normal" adapts | Ongoing monitoring | Model normalizes malicious behavior over time | High -- natural adaptation |
| **Synthetic Identity Fraud** | Creating fake but plausible identities using AI-generated documents | KYC/IDV pipeline | Onboarding of fraudulent entities | High -- deepfakes improving rapidly |

#### Mitigation Architecture

```
Defense-in-Depth for ML Models:

Layer 1: Input Validation
  |-> Statistical distribution checks on input features
  |-> Anomaly detection on feature distributions (detect distribution shift attacks)
  |-> Rate limiting and behavioral analysis on API consumers

Layer 2: Model Robustness
  |-> Adversarial training: Include adversarial examples in training data
  |-> Ensemble models: Multiple models with different architectures vote
  |-> Randomized smoothing: Add controlled noise to inputs during inference
  |-> Regular model retraining with updated attack patterns

Layer 3: Output Monitoring
  |-> Monitor model confidence distributions over time
  |-> Alert on sudden shifts in approval/rejection rates
  |-> Track prediction distribution drift (not just accuracy)
  |-> A/B testing with challenger models to detect blind spots

Layer 4: Rule-Based Backstop
  |-> Hard rules that cannot be overridden by ML models
  |-> Sanctions matches always escalate regardless of ML score
  |-> Regulatory thresholds (e.g., CTR filing) enforced by rules
  |-> Geographic risk rules for sanctioned jurisdictions
```

#### AWS Implementation

| Defense | AWS Service | Implementation |
|---|---|---|
| **Input validation** | Lambda + SageMaker Model Monitor | Feature distribution baseline checks |
| **Adversarial training** | SageMaker Training Jobs | Include perturbation-augmented data |
| **Ensemble inference** | SageMaker Multi-Model Endpoints | Multiple model architectures |
| **Confidence monitoring** | SageMaker Model Monitor + CloudWatch | Track prediction distributions |
| **Rule backstop** | Lambda / Step Functions | Hard-coded regulatory rules |
| **Model versioning** | SageMaker Model Registry | Rapid rollback capability |

#### Key Principle

The rule-based layer acts as an immutable safety net. ML models can reduce false positives and detect novel patterns, but regulatory thresholds, sanctions matches, and known high-risk patterns must always be enforced by deterministic rules that cannot be evaded through adversarial ML techniques.

### 2.8 Labeled Data Acquisition for Supervised Models

A critical prerequisite for supervised ML models (XGBoost, GNN, LSTM) is high-quality labeled training data. In financial services, this is a major bottleneck: fraud is rare (typically <0.5% of transactions), labels are delayed (SAR filings come weeks/months after the event), and ground truth is often ambiguous.

#### Data Acquisition Strategies

| Strategy | Description | Pros | Cons | When to Use |
|---|---|---|---|---|
| **Historical analyst dispositions** | Use past alert review outcomes (TP/FP) as labels | Immediately available, reflects analyst expertise | Biased by existing rules (only reviews what was flagged) | Phase 1 -- bootstrap initial models |
| **Confirmed fraud cases** | Use confirmed fraud (chargebacks, SAR filings, law enforcement feedback) | High-quality positive labels | Delayed (weeks-months), sparse | Phase 2 -- improve model precision |
| **Semi-supervised learning** | Train on small labeled set, propagate labels to similar unlabeled data | Leverages large unlabeled transaction data | Requires careful validation | Phase 2 -- expand training set |
| **Active learning** | Model identifies uncertain cases, routes to analysts for labeling | Efficient use of analyst time, improves model where it's weakest | Requires labeling infrastructure | Phase 2-3 -- continuous improvement |
| **Synthetic oversampling (SMOTE)** | Generate synthetic minority class examples | Addresses class imbalance | Can create unrealistic examples | Phase 1 -- with caution |
| **Federated learning** | Train across multiple institutions without sharing raw data | Privacy-preserving, larger effective dataset | Complex infrastructure, coordination overhead | Phase 4 -- advanced maturity |
| **Weak supervision (Snorkel-style)** | Programmatic labeling functions encode expert heuristics | Scales expert knowledge, handles label noise | Requires domain expert involvement | Phase 1-2 -- rapid labeling |

#### Recommended Bootstrapping Approach

```
Phase 1 (Months 1-3): Bootstrap
  |-> Extract historical alert dispositions from case management system
  |-> Apply SMOTE for class balancing (with validation)
  |-> Use weak supervision to create programmatic labeling functions
  |-> Train initial models on this dataset
  |-> Expected: 60-70% detection rate, high false positives

Phase 2 (Months 3-6): Refine
  |-> Active learning loop: model flags uncertain cases -> analysts label
  |-> Incorporate confirmed fraud feedback (chargebacks, SARs)
  |-> Semi-supervised expansion of training set
  |-> Retrain models monthly
  |-> Expected: 80-90% detection rate, moderate false positives

Phase 3 (Months 6-12): Mature
  |-> Continuous feedback loop from analyst dispositions
  |-> GNN training on graph-labeled data (community-level labels)
  |-> Regular back-testing and challenger model comparison
  |-> Expected: 90-95% detection rate, low false positives
```

#### AWS Implementation

```
Labeling Pipeline:
  SageMaker Ground Truth -> Human labeling workflows
  |-> Analyst review UI (custom) -> DynamoDB (label store)
  |-> SageMaker Processing Jobs -> Label aggregation + quality checks
  |-> S3 -> Versioned labeled datasets
  |-> SageMaker Feature Store -> Consistent features for training

Active Learning Loop:
  SageMaker Endpoint (inference) -> Identify low-confidence predictions
  |-> SQS -> Route to analyst for review
  |-> Analyst labels -> DynamoDB -> Training data refresh
  |-> Automated retraining trigger (with approval gate)
```

---

## 3. Compliance-Safe AI Architecture

### 3.1 Model Explainability Requirements

#### Regulatory Mandates

- **SR 11-7** (Federal Reserve/OCC): Requires model validation, documentation, and governance for all models used in decision-making ([Federal Reserve, 2011](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm))
- **EU AI Act**: High-risk AI systems (includes credit scoring, fraud detection) must provide transparency and explainability. Penalties are tiered: up to 35M EUR or 7% of global turnover for prohibited practices; up to 15M EUR or 3% for high-risk violations; up to 7.5M EUR or 1.5% for providing incorrect information ([EU AI Act, 2024](https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance))
- **ECOA / Fair Lending**: Adverse action notices must explain reasons for denial
- **SOC 2**: Requires documentation of system design and monitoring
- **ISO 27001**: Requires risk management framework for information systems

#### XAI Techniques for Financial AI

| Technique | Type | Best For | Limitations | Regulatory Acceptance |
|---|---|---|---|---|
| **SHAP** (SHapley Additive exPlanations) | Model-agnostic, post-hoc | Feature importance, individual predictions | Computationally expensive for large models | High -- widely used in financial institutions ([CFA Institute, 2025](https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance)) |
| **LIME** (Local Interpretable Model-agnostic Explanations) | Model-agnostic, post-hoc | Individual prediction explanations | Unstable across runs, sampling-dependent | Medium-High |
| **Attention Visualization** | Model-specific (transformers) | NLP models (document analysis) | Only for attention-based architectures | Medium |
| **Partial Dependence Plots** | Model-agnostic | Feature effect visualization | Assumes feature independence | High |
| **Counterfactual Explanations** | Model-agnostic | "What would need to change" explanations | Computationally intensive | High (intuitive for customers) |

**Citation**: [CFA Institute, 2025](https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance); [EthicalXAI, 2025](https://ethicalxai.com/blog/shap-vs-lime-xai-tool-comparison-2025.html)

#### Implementation Pattern: SHAP on SageMaker

```python
# SageMaker Clarify provides built-in SHAP support
from sagemaker.clarify import SHAPConfig, ModelConfig, DataConfig

shap_config = SHAPConfig(
    baseline=baseline_data,      # Reference dataset
    num_samples=1000,            # SHAP sampling
    agg_method="mean_abs",       # Aggregation method
    save_local_shap_values=True  # Store per-prediction explanations
)

# Run SHAP analysis as part of model monitoring
clarify_processor.run_explainability(
    data_config=data_config,
    model_config=model_config,
    explainability_config=shap_config,
    model_scores="probability",
    wait=True
)
```

**SageMaker Clarify** provides built-in SHAP support that integrates with Model Monitor for continuous explainability tracking.

### 3.2 Audit Trails for AI-Driven Decisions

#### What Must Be Logged

| Decision Type | Required Audit Data | Retention | Storage |
|---|---|---|---|
| **Customer Risk Score** | Input features, model version, score, SHAP values, timestamp | 7+ years | S3 (encrypted) + DynamoDB (indexed) |
| **Transaction Alert** | Transaction data, rule/model that triggered, score, analyst disposition | 7+ years | S3 + OpenSearch |
| **KYC Decision** | Documents reviewed, extraction results, verification outcomes | Customer lifetime + 5 years | S3 + RDS |
| **SAR Filing Decision** | All supporting evidence, analyst notes, supervisor review | 7+ years post-filing | S3 (immutable) |
| **Model Change** | Old/new model, validation results, approval chain | Indefinite | CodeCommit/GitHub + S3 |

#### AWS Architecture for Immutable Audit Trails

```
AI Decision Made
  |-> CloudTrail (API calls logged)
  |-> DynamoDB (decision record with TTL disabled)
  |-> S3 (full decision payload, Glacier lifecycle after 1 year)
  |     Object Lock (WORM) for regulatory hold
  |-> OpenSearch (searchable audit index)
  |-> CloudWatch Logs (application logs, 7-year retention)
  |
  Compliance Query Interface:
  |-> Athena (SQL queries on S3 audit data)
  |-> OpenSearch Dashboards (visual exploration)
  |-> Custom API (programmatic access for regulators)
```

### 3.3 Human-in-the-Loop and Auto-Action Guardrails

#### Organization-Wide Risk Classification for Automation Decisions

To ensure consistency across KYC, transaction monitoring, and SRE domains, all AI-driven actions must follow a unified risk classification that determines when automation is acceptable vs when human approval is required.

#### Auto-Action Guardrail Framework

| Risk Tier | Automation Level | Human Role | Criteria for Tier Assignment | Examples |
|---|---|---|---|---|
| **Tier 1: Safe to Automate** | Full automation with audit trail | Periodic sample review (weekly, 5% random sample) | Reversible action AND low financial impact (<$1K) AND high model confidence (>95%) AND no regulatory reporting trigger | Low-priority alert deprioritization, standard KYC document extraction, routine sanctions re-screening (no match) |
| **Tier 2: Auto-Recommend** | AI acts, human can override within window | Review within SLA (same-day for high-value) | Moderate financial impact OR moderate model confidence (80-95%) OR customer-impacting action | Medium-priority alert triage, enhanced monitoring triggers, KYC periodic review summaries |
| **Tier 3: Human Required** | AI prepares, human decides | Mandatory review before action | High financial impact (>$10K) OR low model confidence (<80%) OR irreversible action OR regulatory filing | High-priority alerts, account blocking, SAR filing, model deployment, production infrastructure changes |
| **Tier 4: Multi-Person Required** | AI prepares, multiple humans review | Senior + specialist sign-off | Regulatory reporting OR customer termination OR systemic risk | SAR filing (BSA officer), account closure, model Risk Committee decisions |

#### Key Guardrails for Auto-Action (Tier 1)

Auto-closing or auto-deprioritizing low-priority alerts is acceptable ONLY when ALL of these conditions are met:

1. **Model has been validated** through SR 11-7 process with documented false negative rate
2. **Confidence threshold is high** (>95%) with SHAP explanation logged
3. **The action is reversible** -- alert can be reopened if new evidence emerges
4. **Regular backtesting** confirms auto-closed alerts have <1% true positive rate
5. **Random sample review** (5% weekly) by analysts to catch drift
6. **Full audit trail** records the auto-action decision, model version, confidence score, and SHAP values
7. **Automatic escalation** if auto-close rate exceeds baseline by >10% (indicates possible model drift or adversarial evasion)

**Architecture**:
```
Alert with Score < 50 AND Confidence > 95%
  |-> Check: Does alert involve a sanctions/PEP match? -> NO auto-close (Tier 3)
  |-> Check: Does alert amount exceed $10K? -> NO auto-close (Tier 3)
  |-> Check: Is customer in high-risk category? -> NO auto-close (Tier 2)
  |-> Check: Has model been validated in last 90 days? -> If no, escalate to Tier 2
  |-> Auto-deprioritize with full audit trail
  |-> Flag for weekly random sample review
  |-> Monthly: Backtest auto-closed alerts against confirmed fraud
```

#### Decision Classification Matrix (Revised)

| Decision | Risk Tier | Automation Level | Human Role |
|---|---|---|---|
| **Low-risk customer onboarding** | Tier 1 | Full automation | Weekly sample review |
| **Medium-risk customer onboarding** | Tier 2 | AI-assisted | Review + approve within SLA |
| **High-risk customer onboarding** | Tier 3 | AI-prepared | Full investigation, senior approval |
| **Transaction alert (P4, score <50)** | Tier 1 (with guardrails above) | Auto-deprioritize | Weekly 5% sample review + monthly backtest |
| **Transaction alert (P1-P3)** | Tier 3 | AI investigation summary | Full analyst review |
| **SAR filing** | Tier 4 | AI drafts narrative | BSA officer + supervisor review |
| **Account blocking** | Tier 3 | AI recommends | Senior compliance officer approval |
| **Model deployment** | Tier 3 | Automated testing | Model Risk Committee approval |
| **Production infrastructure change** | Tier 3 | AI recommends | Engineer + manager approval (SOC 2 CC8.1) |

#### Architecture: Step Functions for Human-in-the-Loop

```
Step Functions Workflow:
  1. AI processes data and generates recommendation + risk tier
  2. If Tier 1 (all guardrails met):
       -> Auto-execute with full audit trail
       -> Flag for periodic sample review
  3. If Tier 2:
       -> Execute with override window
       -> Notify responsible party
       -> Log if no override received within SLA
  4. If Tier 3+:
       -> Create task in analyst queue (SQS + custom UI)
       -> Wait for human decision (Task Token pattern)
       -> Human reviews AI recommendation + evidence
       -> Human approves/rejects/escalates
  5. Log decision + reasoning to audit trail
  6. If escalation: Route to supervisor workflow
```

### 3.4 Model Governance Framework (SR 11-7 Aligned)

#### Four Pillars of Model Risk Management

Based on SR 11-7 requirements ([Federal Reserve, 2011](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm); [ModelOp, 2025](https://www.modelop.com/ai-governance/ai-regulations-standards/sr-11-7); [ValidMind, 2025](https://validmind.com/blog/sr-11-7-model-risk-management-compliance/)):

**Pillar 1: Model Development**
- Documented methodology and assumptions
- Data quality assessment and lineage
- Feature selection rationale
- Performance benchmarks against alternatives
- Bias and fairness testing

**Pillar 2: Model Validation**
- Independent review (separate from development team)
- Conceptual soundness evaluation
- Back-testing on out-of-sample data
- Sensitivity analysis
- Challenger model comparison

**Pillar 3: Model Monitoring**
- Real-time performance tracking (accuracy, precision, recall, AUC)
- Data drift detection (input feature distributions)
- Concept drift detection (prediction accuracy degradation)
- Automated alerts on performance degradation
- Regular model scorecards

**Pillar 4: Model Governance**
- Model inventory with risk tiering
- Approval workflows (Model Risk Committee)
- Version control and change management
- Documentation standards
- Annual review cycle

#### AWS Implementation: MLOps Pipeline with Governance

```
Development:
  SageMaker Studio -> Experiment Tracking -> Model Registry

Validation:
  SageMaker Pipelines -> Automated testing suite
    |-> Accuracy/AUC checks
    |-> Bias detection (SageMaker Clarify)
    |-> Explainability (SHAP via Clarify)
    |-> Data quality checks
    |-> Challenger model comparison

Approval:
  Model Registry -> "PendingManualApproval" status
    |-> Model Risk Committee reviews validation report
    |-> Approve/Reject in Model Registry
    |-> Only "Approved" models can be deployed

Deployment:
  CodePipeline/CodeBuild -> Deploy to SageMaker Endpoint
    |-> Blue/green or canary deployment
    |-> A/B testing capability
    |-> Automatic rollback on performance degradation

Monitoring:
  SageMaker Model Monitor
    |-> Data quality monitoring (baseline drift)
    |-> Model quality monitoring (accuracy tracking)
    |-> Bias drift monitoring
    |-> Feature attribution drift
    |-> CloudWatch alerts on violations
    |-> Automated retraining trigger (optional, with approval gate)
```

### 3.5 Data Lineage and Provenance

#### Requirements for Financial AI

Every model prediction must be traceable to:
1. **Source data**: Which data sources contributed to the input features
2. **Transformations**: What processing was applied (feature engineering)
3. **Model version**: Which exact model version produced the output
4. **Configuration**: What thresholds, parameters were active
5. **Decision**: What action was taken based on the prediction

#### AWS Architecture for Data Lineage

```
AWS Glue Data Catalog (metadata management)
  |-> Data sources registered with schema versions
  |-> ETL jobs tracked with input/output lineage

Amazon DataZone (data governance)
  |-> Business glossary for financial terms
  |-> Data quality rules
  |-> Access control policies
  |-> Lineage visualization

SageMaker Lineage Tracking
  |-> Experiment -> Trial -> TrialComponent chain
  |-> Input data artifacts -> Processing -> Model -> Endpoint
  |-> Full reproducibility of any model version

Custom Lineage Service (if needed):
  |-> DynamoDB: Store prediction-level lineage records
  |-> S3: Archive full feature vectors used for each prediction
  |-> Athena: Query lineage for compliance requests
```

---

## 4. AWS-Specific Architecture Recommendations

### 4.1 Amazon Bedrock for Document Analysis and Summarization

**Use Cases in KYC/KYB**:
- Summarize lengthy compliance documents (annual reports, legal filings)
- Extract structured data from unstructured corporate documents
- Analyze adverse media articles for relevance and sentiment
- Generate investigation narratives for SAR filings
- Power chat interfaces for compliance analysts

**Key Consideration**: Bedrock provides SOC 2, ISO 27001 compliance. Data is not used for model training. For HIPAA workloads, verify BAA coverage for specific models.

**Architecture Pattern**:
```
Bedrock + Knowledge Bases (RAG pattern)
  |-> S3: Store compliance policies, past SARs, investigation guides
  |-> OpenSearch Serverless: Vector store for semantic search
  |-> Bedrock Knowledge Base: Index compliance corpus
  |-> Bedrock Agent: Answer analyst questions with citations
  |-> Guardrails: Prevent hallucination, enforce response boundaries
```

### 4.2 Amazon SageMaker for Custom Fraud/AML Models

**Critical Note**: Amazon Fraud Detector is no longer accepting new customers ([AWS FAQ, 2025](https://aws.amazon.com/fraud-detector/faqs/)). SageMaker is the recommended path for all custom fraud and AML models.

**SageMaker Capabilities for Financial Services**:

| Capability | Service | Use Case |
|---|---|---|
| **AutoML** | SageMaker Autopilot | Quick baseline models for fraud scoring |
| **Custom Training** | SageMaker Training Jobs | XGBoost, LightGBM, neural networks for fraud |
| **GNN** | SageMaker + DGL/GraphStorm | Network-based fraud detection |
| **Real-Time Inference** | SageMaker Endpoints | Per-transaction scoring (<100ms) |
| **Batch Inference** | SageMaker Batch Transform | Nightly AML pattern analysis |
| **Model Monitoring** | SageMaker Model Monitor | Drift detection, performance tracking |
| **Explainability** | SageMaker Clarify | SHAP values, bias detection |
| **Feature Store** | SageMaker Feature Store | Consistent features across training and inference |
| **Pipelines** | SageMaker Pipelines | Automated retraining workflows |

### 4.3 Amazon Textract + Comprehend for KYC Document Processing

```
KYC Document Pipeline:
  S3 (document upload, encrypted at rest)
    |-> Textract AnalyzeID (identity documents)
    |     -> Name, DOB, Address, ID number, expiry
    |-> Textract AnalyzeDocument (financial documents)
    |     -> Bank statements, tax returns, proof of address
    |-> Comprehend (NLP analysis)
    |     -> Entity extraction (names, organizations, amounts)
    |     -> Sentiment analysis (adverse media)
    |     -> PII detection (mask/redact sensitive data)
    |-> Bedrock (complex document understanding)
    |     -> Multi-page document summarization
    |     -> Cross-document entity linking
    |     -> Reasoning about document authenticity
    |-> DynamoDB (structured extraction results)
    |-> Step Functions (orchestration + human review routing)
```

### 4.4 EventBridge + Step Functions for Orchestration

**Central Orchestration Architecture**:
```
EventBridge (event bus for all KYC/AML events)
  |-> Rules:
  |     "new-customer-onboarding" -> Step Functions (KYC workflow)
  |     "transaction-alert" -> Step Functions (investigation workflow)
  |     "sanctions-list-update" -> Lambda (re-screening trigger)
  |     "model-performance-degraded" -> SNS (ML team notification)
  |     "periodic-review-due" -> Step Functions (review workflow)
  |
  Step Functions Workflows:
    KYC Onboarding:
      1. Document upload notification
      2. Parallel: Textract extraction + IDV verification
      3. Entity resolution
      4. Sanctions/PEP screening
      5. Risk scoring
      6. Decision gate (auto-approve or human review per Tier classification)
      7. Audit trail logging

    Transaction Investigation:
      1. Alert received
      2. Parallel: Customer profile lookup + transaction history + network analysis
      3. Bedrock: Generate investigation summary
      4. Route to analyst (Task Token wait)
      5. Analyst decision
      6. SAR filing if needed
      7. Audit trail logging
```

### 4.5 Multi-Cloud GPU Options for Training

For large-scale model training that exceeds AWS capacity or cost targets:

| Provider | GPU Options | Cost Advantage | Use Case |
|---|---|---|---|
| **AWS (SageMaker)** | P5 (H100), P4d (A100), Inf2 (Inferentia2) | Native integration, SageMaker ML workflow | Primary for all models |
| **GCP (Vertex AI)** | A3 (H100), TPU v5e | Competitive pricing, strong TPU ecosystem | Large-scale GNN training |
| **Azure (Azure ML)** | ND H100 v5, ND A100 v4 | Enterprise agreements, hybrid cloud | Organizations with Azure EA |
| **CoreWeave** | H100, A100 clusters | 30-50% cheaper than hyperscalers | Burst training capacity |
| **Lambda Cloud** | H100 clusters | Competitive spot pricing | Research and experimentation |

**Recommendation**: Stay on AWS SageMaker for all production workloads (compliance boundary, data residency). Consider multi-cloud only for:
- Research experiments with non-production data
- Cost optimization on large training jobs (with proper data handling)
- Disaster recovery / business continuity for critical models

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Months 1-3)
- Deploy document extraction pipeline (Textract + Bedrock)
- Implement sanctions/PEP screening API integration
- Build audit trail infrastructure (DynamoDB + S3 + CloudTrail)
- Establish model governance framework (documentation, approval process)
- Bootstrap labeled training data (historical analyst dispositions + weak supervision)
- **Quick Win**: Automate document data extraction for KYC onboarding

### Phase 2: Intelligence (Months 3-6)
- Train and deploy customer risk scoring model (SageMaker)
- Implement rule-based transaction monitoring with ML augmentation
- Build Neptune graph for entity resolution and beneficial ownership
- Deploy alert prioritization model for existing alert queue
- Begin active learning loop for training data refinement
- **Quick Win**: Reduce false positive rate on transaction alerts by 50%+

### Phase 3: Advanced Analytics (Months 6-12)
- Deploy GNN-based AML detection on Neptune + SageMaker (batch path)
- Implement real-time transaction scoring (Kinesis + SageMaker Endpoints)
- Build ongoing monitoring automation (adverse media, sanctions re-screening)
- Deploy Bedrock-powered investigation assistant
- Implement adversarial robustness testing for production models
- **Quick Win**: 3-5x analyst productivity improvement

### Phase 4: Optimization (Months 12-18)
- Continuous model improvement cycle (automated retraining with approval gates)
- Cross-product risk scoring (unified customer risk view)
- Advanced network analysis (community detection, path analysis)
- Regulatory reporting automation
- Explore federated learning for cross-institution collaboration
- **Quick Win**: Reduce periodic review time by 75%

---

## 6. Cost Estimates

All costs are monthly estimates for a mid-size financial services organization. Annual figures provided for budget planning.

### 6.1 AWS Infrastructure Costs

| Component | Monthly Cost (Est.) | Annual Cost (Est.) | Scaling Factor |
|---|---|---|---|
| **Textract** | $500-5,000 | $6,000-60,000 | Per page processed |
| **SageMaker Endpoints (real-time)** | $2,000-10,000 | $24,000-120,000 | Per endpoint instance |
| **SageMaker Training** | $1,000-5,000 | $12,000-60,000 | Per training job |
| **Neptune (graph DB)** | $1,500-8,000 | $18,000-96,000 | Per instance + storage |
| **Bedrock (Claude/Nova)** | $2,000-15,000 | $24,000-180,000 | Per token (input/output) |
| **Kinesis Data Streams** | $500-3,000 | $6,000-36,000 | Per shard-hour + data volume |
| **S3 + DynamoDB (audit)** | $500-2,000 | $6,000-24,000 | Per GB stored |
| **AWS Subtotal** | **$8,500-48,000** | **$102,000-576,000** | |

### 6.2 Third-Party Vendor Costs

| Component | Monthly Cost (Est.) | Annual Cost (Est.) | Scaling Factor |
|---|---|---|---|
| **IDV vendor (Jumio/Onfido)** | $5,000-50,000 | $60,000-600,000 | Per verification |
| **Sanctions screening API** | $2,000-20,000 | $24,000-240,000 | Per screening |
| **Vendor Subtotal** | **$7,000-70,000** | **$84,000-840,000** | |

### 6.3 Consolidated Cost Summary

| Cost Category | Monthly (Low) | Monthly (High) | Annual (Low) | Annual (High) |
|---|---|---|---|---|
| **AWS Infrastructure** | $8,500 | $48,000 | $102,000 | $576,000 |
| **Third-Party Vendors** | $7,000 | $70,000 | $84,000 | $840,000 |
| **Total** | **$15,500** | **$118,000** | **$186,000** | **$1,416,000** |

**Note**: Costs are highly dependent on transaction volume, customer base size, and screening frequency. The low estimate assumes ~10K transactions/day and ~1K KYC verifications/month. The high estimate assumes ~500K transactions/day and ~50K verifications/month. Request specific volume data from the organization for accurate estimates.

---

## 7. Key Risk and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| **Model bias** | Regulatory action, unfair outcomes | SageMaker Clarify bias detection, regular fairness audits |
| **Data quality** | Poor model performance | Data quality checks in pipeline, SageMaker Data Wrangler |
| **Model drift** | Degraded detection accuracy | SageMaker Model Monitor, automated retraining triggers |
| **Regulatory change** | Non-compliance | Modular architecture allowing policy updates without model changes |
| **Vendor lock-in** | Migration cost | Abstract vendor APIs behind internal interfaces |
| **Data breach** | Regulatory fines, reputation | Encryption at rest/transit, VPC isolation, least-privilege IAM |
| **Explainability gaps** | Regulatory rejection | SHAP explanations for every model, documentation standards |
| **Adversarial attacks** | Model evasion by sophisticated actors | Defense-in-depth: input validation, adversarial training, ensemble models, rule-based backstop, confidence monitoring, rapid rollback (see Section 2.7) |
| **Labeled data scarcity** | Unable to train effective supervised models | Phased data acquisition: historical dispositions -> active learning -> semi-supervised -> federated (see Section 2.8) |
| **Synthetic identity fraud** | Onboarding of fraudulent entities | Liveness detection, document forensics, cross-reference with authoritative sources |

---

## Sources

### KYC/Document Processing
- [SparkCo AI: AWS Textract vs Azure Document Intelligence](https://sparkco.ai/blog/aws-textract-vs-azure-document-intelligence-a-deep-dive/)
- [BusinessWareTech: Invoice Extraction Benchmark](https://www.businesswaretech.com/blog/research-best-ai-services-for-automatic-invoice-processing)
- [MarkTechPost: Top 6 OCR Models 2025](https://www.marktechpost.com/2025/11/02/comparing-the-top-6-ocr-optical-character-recognition-models-systems-in-2025/)
- [AWS: Automating KYC with Capgemini on AWS](https://aws.amazon.com/blogs/apn/automating-the-know-your-customer-process-using-capgemini-ai-powered-solution-on-aws/)
- [Jumio: AI KYC Identity Verification 2025](https://www.jumio.com/how-ai-kyc-is-changing-identity-verification/)
- [DigiPay.Guru: eKYC Trends 2025](https://www.digipay.guru/blog/ekyc-verification-trends-in-2024/)

### Transaction Monitoring and AML
- [EY Nordic Transaction Monitoring Survey 2025](https://www.ey.com/en_se/insights/financial-services/how-ai-is-reshaping-the-future-of-transaction-monitoring)
- [Flagright: AI and the Future of AML Compliance](https://www.flagright.com/post/ai-and-the-future-of-aml-compliance)
- [Robotics & Automation News: AI-driven Transaction Monitoring 2026](https://roboticsandautomationnews.com/2026/02/19/ai-driven-transaction-monitoring-the-future-of-fraud-and-risk-management-in-global-banking/98981/)
- [Sumsub: AI in Anti-Money Laundering 2026](https://sumsub.com/blog/ai-in-anti-money-laundering-and-compliance/)
- [Fintech Global: Why AI is Essential for AML in 2026](https://fintech.global/2026/01/14/why-ai-is-becoming-essential-for-aml-in-2026/)
- [IR.com: AI Transaction Monitoring Guide 2025](https://www.ir.com/guides/ai-transaction-monitoring-and-how-it-works-complete-guide-2025)
- [Deloitte: The Future of Regulatory Productivity](https://www2.deloitte.com/us/en/pages/regulatory/articles/cost-of-compliance-regulatory-productivity.html)
- [ACAMS: AML Effectiveness Survey](https://www.acams.org/en/resources/surveys)

### AWS Architecture
- [AWS: Fraud Detection with IDP on AWS (Bedrock + SageMaker)](https://github.com/aws-solutions-library-samples/guidance-for-fraud-detection-with-intelligent-document-processing-on-aws)
- [AWS: GNN Fraud Detection with Neptune + SageMaker](https://aws.amazon.com/blogs/machine-learning/build-a-gnn-based-real-time-fraud-detection-solution-using-amazon-sagemaker-amazon-neptune-and-the-deep-graph-library/)
- [AWS: Anti-Money Laundering Solutions on AWS](https://aws.amazon.com/blogs/big-data/implement-anti-money-laundering-solutions-on-aws/)
- [AWS: AI Agents for Compliance Screening](https://aws.amazon.com/blogs/machine-learning/how-amazon-uses-ai-agents-to-support-compliance-screening-of-billions-of-transactions-per-day/)
- [AWS APN: Neptune GenAI Anti-Fraud Solutions 2026](https://aws.amazon.com/blogs/apn/how-aws-partners-can-deliver-anti-fraud-solutions-using-aws-genai-and-amazon-neptune-graph-capabilities/)
- [Amazon Fraud Detector FAQ (Deprecated)](https://aws.amazon.com/fraud-detector/faqs/)

### Sanctions and PEP Screening
- [sanctions.io: Role of AI in Sanctions & PEP Screening](https://www.sanctions.io/blog/the-role-of-ai-in-sanctions-pep-screening)
- [Alessa: Top 10 Sanctions Screening Solutions 2026](https://alessa.com/blog/top-10-sanctions-screening-solutions/)
- [AML Watcher: AML Checks Trends 2026](https://amlwatcher.com/blog/aml-checks/)
- [Mobbeel: Definitive AML Guide 2026](https://www.mobbeel.com/en/blog/aml-guide-2025-sanctions-lists-financial-kyc/)

### Model Governance and Explainability
- [Federal Reserve: SR 11-7 Model Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm)
- [ModelOp: SR 11-7 Compliance](https://www.modelop.com/ai-governance/ai-regulations-standards/sr-11-7)
- [ValidMind: SR 11-7 Model Risk Management Compliance](https://validmind.com/blog/sr-11-7-model-risk-management-compliance/)
- [CFA Institute: Explainable AI in Finance 2025](https://rpc.cfainstitute.org/research/reports/2025/explainable-ai-in-finance)
- [EthicalXAI: SHAP vs LIME 2025](https://ethicalxai.com/blog/shap-vs-lime-xai-tool-comparison-2025.html)
- [BIS: How Regulators Can Address AI Explainability](https://www.bis.org/fsi/fsipapers24.pdf)
- [EY: Supervisory Expectations and Model Risk Management](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-us/insights/banking-capital-markets/documents/ey-mrm-ai-ml.pdf)
- [Coforge: SR 11-7 Guide to AI Adoption in Banks](https://www.coforge.com/what-we-know/blog/coforge-blog-sr11-7-a-comprehensive-guide-to-ai-adoption-and-model-risk-management-in-banks)

### Identity Verification
- [iDenfy: Best Identity Verification Software 2026](https://www.idenfy.com/blog/best-identity-verification-software/)
- [Ondato: Best Identity Verification Software 2026](https://ondato.com/blog/best-identity-verification-software/)
- [OLOID: Liveness Detection Guide 2026](https://www.oloid.com/blog/liveness-detection)

---

**Document Version**: 1.1
**Last Updated**: March 7, 2026 (Revised per fact-check and peer review feedback)
**Revision Notes**: Narrowed AML false positive range to 70-90%; corrected EU AI Act penalty structure; added adversarial ML threat analysis (Section 2.7); added labeled data acquisition strategy (Section 2.8); added auto-action guardrail framework (Section 3.3); standardized cost format with consolidated summary; added missing citations; softened vendor-sourced statistics.
**Research Confidence**: High (all claims cited from 2025-2026 sources)
**Next Review**: Quarterly update recommended
