# AI Incident Intelligence Agent - System Architecture

**Project**: GenAI Enablement - Observability Solution
**Version**: 1.0
**Date**: December 2, 2025
**Status**: Design Phase

---

## 1. Executive Summary

The AI Incident Intelligence Agent is an autonomous system that monitors AWS infrastructure (EKS, RDS, EC2, Lambda, etc.), responds to CloudWatch/EventBridge alerts in real-time, and provides intelligent, contextual notifications to on-call engineers.

### Key Capabilities
- ✅ Real-time alert ingestion from AWS CloudWatch/EventBridge
- ✅ Automated context gathering (logs, metrics, traces, historical incidents)
- ✅ AI-powered root cause analysis and impact assessment
- ✅ Intelligent runbook matching and suggestions
- ✅ Enriched notifications to Slack/PagerDuty/MS Teams
- ✅ Learning from historical incidents and engineer feedback

### Expected Impact
- **50-70%** reduction in MTTR (time to understand incident)
- **60-80%** reduction in alert noise (intelligent filtering)
- **40-60%** less context switching for on-call engineers
- **30-50%** faster incident triage

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AWS INFRASTRUCTURE LAYER                          │
├─────────────────────────────────────────────────────────────────────────┤
│  EKS Clusters  │  RDS Databases  │  EC2 Instances  │  Lambda Functions  │
│  Load Balancers │  API Gateway   │  S3 Buckets     │  DynamoDB Tables   │
└────────┬────────────────┬─────────────────┬──────────────────┬──────────┘
         │                │                 │                  │
         ▼                ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      MONITORING & ALERTS LAYER                           │
├─────────────────────────────────────────────────────────────────────────┤
│                     Amazon CloudWatch Alarms                             │
│                     CloudWatch Logs Insights                             │
│                     AWS X-Ray (Distributed Tracing)                      │
│                     Container Insights (EKS)                             │
│                     RDS Enhanced Monitoring                              │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       EVENT ROUTING LAYER                                │
├─────────────────────────────────────────────────────────────────────────┤
│                    Amazon EventBridge Rules                              │
│                    SNS Topics (for broadcasting)                         │
│                    SQS Queues (for buffering)                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI AGENT ORCHESTRATION LAYER                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │              Lambda Trigger Handler                          │        │
│  │  - Validates incoming events                                 │        │
│  │  - Deduplicates alerts                                       │        │
│  │  - Routes to appropriate workflow                            │        │
│  └──────────────────┬───────────────────────────────────────────┘        │
│                     │                                                     │
│                     ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │          LangGraph Agent Engine (ECS/Fargate)                │        │
│  │                                                               │        │
│  │  ┌──────────────────────────────────────────────────┐        │        │
│  │  │  State Machine Workflow                          │        │        │
│  │  │  ┌────────────────────────────────────────────┐  │        │        │
│  │  │  │  1. Alert Reception & Validation          │  │        │        │
│  │  │  └──────────┬─────────────────────────────────┘  │        │        │
│  │  │             ▼                                      │        │        │
│  │  │  ┌────────────────────────────────────────────┐  │        │        │
│  │  │  │  2. Context Gathering                      │  │        │        │
│  │  │  │     - Recent logs (CloudWatch/OpenSearch) │  │        │        │
│  │  │  │     - Metrics (CloudWatch)                 │  │        │        │
│  │  │  │     - Traces (X-Ray)                       │  │        │        │
│  │  │  │     - Similar past incidents (Vector DB)  │  │        │        │
│  │  │  │     - Resource metadata (AWS APIs)         │  │        │        │
│  │  │  └──────────┬─────────────────────────────────┘  │        │        │
│  │  │             ▼                                      │        │        │
│  │  │  ┌────────────────────────────────────────────┐  │        │        │
│  │  │  │  3. AI Analysis (LLM)                      │  │        │        │
│  │  │  │     - Root cause hypothesis                │  │        │        │
│  │  │  │     - Severity assessment                  │  │        │        │
│  │  │  │     - Impact radius calculation            │  │        │        │
│  │  │  │     - Runbook matching                     │  │        │        │
│  │  │  └──────────┬─────────────────────────────────┘  │        │        │
│  │  │             ▼                                      │        │        │
│  │  │  ┌────────────────────────────────────────────┐  │        │        │
│  │  │  │  4. Notification Enrichment                │  │        │        │
│  │  │  │     - Format for Slack/PagerDuty/Teams     │  │        │        │
│  │  │  │     - Add actionable recommendations       │  │        │        │
│  │  │  │     - Include relevant dashboards/links    │  │        │        │
│  │  │  └──────────┬─────────────────────────────────┘  │        │        │
│  │  │             ▼                                      │        │        │
│  │  │  ┌────────────────────────────────────────────┐  │        │        │
│  │  │  │  5. Delivery & State Persistence           │  │        │        │
│  │  │  └────────────────────────────────────────────┘  │        │        │
│  │  └──────────────────────────────────────────────────┘        │        │
│  │                                                               │        │
│  │  Agent Tools & Capabilities:                                 │        │
│  │  - AWS SDK (boto3) for resource queries                      │        │
│  │  - CloudWatch Logs Insights queries                          │        │
│  │  - X-Ray trace analysis                                       │        │
│  │  - Historical incident search (Vector DB)                    │        │
│  │  - Runbook knowledge base lookup                             │        │
│  └───────────────────────────────────────────────────────────────┘        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        LLM INFERENCE LAYER                               │
├─────────────────────────────────────────────────────────────────────────┤
│  Option 1: AWS SageMaker Endpoint (Self-hosted LLM)                     │
│            - Llama 3, Mistral, or Claude (via Bedrock)                   │
│            - Full control, data privacy                                  │
│                                                                           │
│  Option 2: Amazon Bedrock (Managed)                                     │
│            - Claude 3.5 Sonnet, Claude 3 Haiku                           │
│            - Serverless, pay-per-use                                     │
│                                                                           │
│  Option 3: OpenAI API (External)                                        │
│            - GPT-4, GPT-4 Turbo                                          │
│            - Fastest to prototype (requires data review)                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA & MEMORY LAYER                               │
├─────────────────────────────────────────────────────────────────────────┤
│  DynamoDB Tables:                                                        │
│  - incident_state         (active incidents, agent workflow state)       │
│  - incident_history       (completed incidents, resolutions)             │
│  - agent_memory           (learned patterns, feedback)                   │
│  - runbook_index          (runbook metadata and mappings)                │
│                                                                           │
│  S3 Buckets:                                                             │
│  - incident-artifacts     (logs, traces, screenshots)                    │
│  - runbook-library        (markdown runbooks, playbooks)                 │
│  - training-data          (for fine-tuning, feedback)                    │
│                                                                           │
│  Amazon OpenSearch:                                                      │
│  - Full-text log search                                                  │
│  - Historical incident search                                            │
│                                                                           │
│  Vector Database (OpenSearch with k-NN or Pinecone):                    │
│  - Semantic similarity search for past incidents                         │
│  - Runbook embeddings for smart matching                                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      NOTIFICATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Slack Integration:                                                      │
│  - Rich message blocks with context                                      │
│  - Interactive buttons (acknowledge, escalate, provide feedback)         │
│  - Thread management for updates                                         │
│                                                                           │
│  PagerDuty Integration:                                                  │
│  - Alert creation with enriched context                                  │
│  - Automatic incident linking                                            │
│  - Custom fields with AI analysis                                        │
│                                                                           │
│  MS Teams Integration:                                                   │
│  - Adaptive cards with incident details                                  │
│  - Action buttons for common responses                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. LangGraph Agent Workflow Design

### State Machine Overview

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """State passed through the agent workflow"""
    # Input
    alert_id: str
    alert_source: str  # cloudwatch, eventbridge, etc.
    alert_data: dict
    timestamp: str

    # Context gathering
    logs: list[str]
    metrics: dict
    traces: list[dict]
    similar_incidents: list[dict]
    resource_metadata: dict

    # Analysis
    root_cause_hypothesis: str
    severity: str  # critical, high, medium, low
    impact_assessment: str
    affected_resources: list[str]
    matched_runbooks: list[dict]

    # Actions
    recommended_actions: list[str]
    escalation_needed: bool

    # Notification
    notification_sent: bool
    notification_channels: list[str]

    # Feedback loop
    engineer_feedback: dict
    resolution_summary: str

    # Agent internals
    messages: Annotated[Sequence[BaseMessage], "Agent reasoning trace"]
    next_step: str
```

### Workflow Nodes

```
┌──────────────────────┐
│   START              │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  validate_alert                                          │
│  - Check alert format                                    │
│  - Deduplicate (check if already processing)             │
│  - Extract key metadata                                  │
│  Decision: valid → gather_context | invalid → END        │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  gather_context (parallel execution)                     │
│  - fetch_logs: Query CloudWatch/OpenSearch               │
│  - fetch_metrics: Get relevant CloudWatch metrics        │
│  - fetch_traces: Pull X-Ray traces if available          │
│  - fetch_similar_incidents: Vector search past incidents │
│  - fetch_resource_metadata: AWS API calls                │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  analyze_incident (LLM-powered)                          │
│  Prompt Template:                                        │
│  """                                                     │
│  You are an expert SRE analyzing an AWS infrastructure   │
│  incident. Based on the following information:           │
│                                                          │
│  Alert: {alert_data}                                     │
│  Recent Logs: {logs}                                     │
│  Metrics: {metrics}                                      │
│  Traces: {traces}                                        │
│  Similar Past Incidents: {similar_incidents}             │
│                                                          │
│  Provide:                                                │
│  1. Root cause hypothesis                                │
│  2. Severity assessment (critical/high/medium/low)       │
│  3. Impact assessment (which users/services affected)    │
│  4. List of affected resources                           │
│  5. Recommended immediate actions                        │
│  """                                                     │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  match_runbooks                                          │
│  - Semantic search in runbook library                    │
│  - Match based on:                                       │
│    * Alert type                                          │
│    * Resource type (EKS, RDS, etc.)                      │
│    * Error patterns                                      │
│    * Similar past incidents                              │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  should_escalate (decision node)                         │
│  Conditions for escalation:                              │
│  - Severity == critical                                  │
│  - No matching runbook found                             │
│  - Similar incident had escalation before                │
│  - Resource is production-critical                       │
│                                                          │
│  Decision: escalate → prepare_escalation                 │
│           no_escalate → enrich_notification              │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  enrich_notification (LLM-powered)                       │
│  Create human-friendly summary:                          │
│  - Executive summary (2-3 sentences)                     │
│  - Technical details                                     │
│  - Recommended actions with runbook links                │
│  - Dashboard links                                       │
│  - Historical context if available                       │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  send_notifications                                      │
│  - Format for each channel (Slack/PagerDuty/Teams)       │
│  - Send notifications                                    │
│  - Store incident in DynamoDB                            │
│  - Create incident thread for updates                    │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  wait_for_feedback (async)                               │
│  - Listen for engineer actions (Slack buttons)           │
│  - Capture:                                              │
│    * Was analysis helpful? (👍/👎)                       │
│    * Actual root cause                                   │
│    * Actions taken                                       │
│    * Time to resolution                                  │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  update_memory                                           │
│  - Store incident with resolution                        │
│  - Update runbook effectiveness metrics                  │
│  - Generate embeddings for future similarity search      │
│  - Update agent learning database                        │
└──────┬───────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│   END                │
└──────────────────────┘
```

---

## 4. AWS Service Integration

### 4.1 Alert Ingestion Flow

```
CloudWatch Alarm State Change
         │
         ├─→ SNS Topic: "infrastructure-alerts"
         │
         ├─→ EventBridge Rule: "route-to-ai-agent"
         │    Pattern: {
         │      "source": ["aws.cloudwatch"],
         │      "detail-type": ["CloudWatch Alarm State Change"]
         │    }
         │
         └─→ SQS Queue: "ai-agent-alert-queue"
              - FIFO for ordering
              - DLQ for failed processing
              - Visibility timeout: 5 minutes
              │
              ▼
         Lambda: "alert-processor"
              - Deduplication
              - Validation
              - Triggers ECS task (LangGraph agent)
```

### 4.2 Context Gathering Integration

**CloudWatch Logs**:
```python
# Query recent logs around alert time
client = boto3.client('logs')
response = client.start_query(
    logGroupName=log_group,
    startTime=alert_time - 300,  # 5 min before
    endTime=alert_time + 60,     # 1 min after
    queryString='''
        fields @timestamp, @message, @logStream
        | filter @message like /ERROR|WARN|Exception/
        | sort @timestamp desc
        | limit 100
    '''
)
```

**CloudWatch Metrics**:
```python
# Fetch relevant metrics
cloudwatch = boto3.client('cloudwatch')
metrics = cloudwatch.get_metric_data(
    MetricDataQueries=[
        {
            'Id': 'cpu',
            'MetricStat': {
                'Metric': {
                    'Namespace': 'AWS/EKS',
                    'MetricName': 'CPUUtilization',
                    'Dimensions': [{'Name': 'ClusterName', 'Value': cluster_name}]
                },
                'Period': 60,
                'Stat': 'Average'
            }
        }
    ],
    StartTime=alert_time - 3600,  # Last hour
    EndTime=alert_time
)
```

**X-Ray Traces**:
```python
# Get trace summaries for errors
xray = boto3.client('xray')
traces = xray.get_trace_summaries(
    StartTime=alert_time - 300,
    EndTime=alert_time,
    FilterExpression='error = true OR fault = true'
)
```

**Resource Metadata**:
```python
# Example: Get EKS cluster details
eks = boto3.client('eks')
cluster = eks.describe_cluster(name=cluster_name)

# RDS instance details
rds = boto3.client('rds')
db_instance = rds.describe_db_instances(DBInstanceIdentifier=db_id)
```

---

## 5. Data Model Design

### 5.1 DynamoDB Tables

#### Table: `incident_state`
**Purpose**: Track active incidents and agent workflow state
**Primary Key**: `incident_id` (partition key)

```json
{
  "incident_id": "inc-2025-12-02-1234",
  "alert_id": "alarm-eks-cpu-spike",
  "status": "analyzing|notified|acknowledged|resolved",
  "created_at": "2025-12-02T10:30:00Z",
  "updated_at": "2025-12-02T10:35:00Z",
  "alert_source": "cloudwatch",
  "resource_type": "eks",
  "resource_id": "my-cluster",
  "severity": "high",
  "workflow_state": {
    "current_node": "analyze_incident",
    "context_gathered": true,
    "analysis_complete": false,
    "notification_sent": false
  },
  "context": {
    "logs": ["..."],
    "metrics": {...},
    "traces": [...]
  },
  "analysis": {
    "root_cause": "CPU spike due to memory leak in pod xyz",
    "impact": "3 pods affected, user-facing API experiencing 500ms latency",
    "confidence": 0.85
  },
  "assigned_engineer": "jane.doe@company.com",
  "notification_channels": ["slack-#incidents", "pagerduty"],
  "ttl": 1733140800  # 7 days retention
}
```

**GSI**: `status-created_at-index` (for querying active incidents)

#### Table: `incident_history`
**Purpose**: Long-term storage of completed incidents
**Primary Key**: `incident_id` (partition key)
**Sort Key**: `resolved_at` (for time-range queries)

```json
{
  "incident_id": "inc-2025-12-01-5678",
  "created_at": "2025-12-01T14:00:00Z",
  "resolved_at": "2025-12-01T14:45:00Z",
  "mttr_seconds": 2700,
  "alert_type": "RDS HighCPU",
  "resource_type": "rds",
  "resource_id": "prod-db-01",
  "severity": "critical",
  "root_cause": "Missing index causing full table scans",
  "resolution": "Created composite index on users(email, created_at)",
  "runbook_used": "runbook-rds-performance-001",
  "runbook_helpful": true,
  "engineer_feedback": {
    "analysis_accuracy": 5,
    "recommendation_quality": 4,
    "time_saved_minutes": 20
  },
  "embedding": [0.123, -0.456, ...]  # For similarity search
}
```

**GSI**: `resource_type-resolved_at-index` (for analytics)

#### Table: `agent_memory`
**Purpose**: Store learned patterns and correlations
**Primary Key**: `pattern_id` (partition key)

```json
{
  "pattern_id": "pattern-eks-oom-001",
  "pattern_type": "alert_correlation",
  "resource_types": ["eks", "cloudwatch"],
  "alert_patterns": [
    "ContainerMemoryUsage > 90%",
    "PodEvicted",
    "NodeNotReady"
  ],
  "common_root_causes": [
    "Memory leak in application",
    "Insufficient memory limits",
    "Memory spike due to batch job"
  ],
  "occurrence_count": 15,
  "success_rate": 0.87,
  "last_seen": "2025-12-02T10:30:00Z",
  "recommended_runbook": "runbook-eks-oom-remediation"
}
```

#### Table: `runbook_index`
**Purpose**: Metadata for runbook library
**Primary Key**: `runbook_id` (partition key)

```json
{
  "runbook_id": "runbook-eks-cpu-spike-001",
  "title": "EKS CPU Spike Investigation and Remediation",
  "resource_types": ["eks", "ec2"],
  "alert_types": ["CPUUtilization", "NodeCPUUtilization"],
  "tags": ["performance", "scaling", "troubleshooting"],
  "s3_path": "s3://runbook-library/eks/cpu-spike-remediation.md",
  "embedding": [0.234, -0.567, ...],
  "usage_count": 42,
  "effectiveness_score": 0.92,
  "last_updated": "2025-11-15T00:00:00Z"
}
```

### 5.2 S3 Bucket Structure

```
s3://ai-incident-agent-artifacts/
├── incidents/
│   └── 2025/
│       └── 12/
│           └── 02/
│               └── inc-2025-12-02-1234/
│                   ├── alert.json
│                   ├── logs.txt
│                   ├── metrics.json
│                   ├── traces.json
│                   ├── analysis.md
│                   └── resolution.md
├── runbooks/
│   ├── eks/
│   │   ├── cpu-spike-remediation.md
│   │   ├── oom-troubleshooting.md
│   │   └── pod-crashloop-debug.md
│   ├── rds/
│   │   ├── high-cpu-analysis.md
│   │   ├── connection-issues.md
│   │   └── slow-queries.md
│   └── lambda/
│       ├── timeout-investigation.md
│       └── memory-errors.md
└── training-data/
    └── feedback/
        └── 2025-12.jsonl
```

### 5.3 Vector Database (OpenSearch k-NN)

**Index**: `incident_embeddings`
**Purpose**: Semantic search for similar past incidents

```json
{
  "mappings": {
    "properties": {
      "incident_id": { "type": "keyword" },
      "incident_text": { "type": "text" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 1536,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      },
      "resource_type": { "type": "keyword" },
      "severity": { "type": "keyword" },
      "resolved_at": { "type": "date" }
    }
  }
}
```

**Query Example**:
```python
# Find similar incidents
query = {
    "query": {
        "knn": {
            "embedding": {
                "vector": current_incident_embedding,
                "k": 5
            }
        }
    },
    "filter": {
        "term": { "resource_type": "eks" }
    }
}
```

---

## 6. Technology Stack

### 6.1 Core Components

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Agent Orchestration** | LangGraph | State machine for complex workflows, native LLM integration |
| **LLM Hosting** | AWS Bedrock (Claude 3.5) | Serverless, pay-per-use, AWS-native, excellent reasoning |
| **Alternative LLM** | SageMaker (Llama 3 70B) | Self-hosted option for data privacy, cost control |
| **Runtime** | AWS ECS Fargate | Serverless containers, scales to zero |
| **Event Processing** | Lambda + SQS + EventBridge | Event-driven, scalable, AWS-native |
| **State Management** | DynamoDB | Serverless NoSQL, fast reads/writes |
| **Vector Search** | OpenSearch with k-NN | Integrated with AWS, semantic search |
| **Object Storage** | S3 | Durable storage for artifacts, runbooks |
| **Logging/Metrics** | CloudWatch | Native AWS observability |
| **Notifications** | Slack API, PagerDuty API | Industry-standard on-call tools |

### 6.2 Python Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
langgraph = "^0.2.0"
langchain = "^0.3.0"
langchain-aws = "^0.2.0"
boto3 = "^1.35.0"
pydantic = "^2.9.0"
python-dotenv = "^1.0.0"
slack-sdk = "^3.33.0"
pypd = "^1.1.0"  # PagerDuty
opensearch-py = "^2.7.0"
sentence-transformers = "^3.3.0"  # For embeddings
redis = "^5.2.0"  # Optional: caching layer
```

### 6.3 Infrastructure as Code (Terraform)

```hcl
# modules/ai-incident-agent/main.tf
module "ai_incident_agent" {
  source = "./modules/ai-incident-agent"

  environment           = "production"
  aws_region           = "us-east-1"
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids

  # LLM Configuration
  llm_provider         = "bedrock"  # or "sagemaker"
  bedrock_model_id     = "anthropic.claude-3-5-sonnet-20241022-v2:0"

  # Compute
  ecs_task_cpu         = 2048
  ecs_task_memory      = 4096

  # Data
  dynamodb_billing_mode = "PAY_PER_REQUEST"
  opensearch_instance_type = "t3.medium.search"

  # Notifications
  slack_webhook_url    = var.slack_webhook
  pagerduty_api_key    = var.pagerduty_api_key

  tags = {
    Project = "GenAI-Enablement"
    Solution = "AI-Incident-Agent"
  }
}
```

---

## 7. Scalability & Reliability

### 7.1 Handling High Alert Volumes

**Challenge**: During outages, hundreds of alerts may fire simultaneously

**Solutions**:
1. **SQS FIFO Queue with Deduplication**
   - Use `MessageDeduplicationId` based on alert signature
   - Prevents processing same alert multiple times
   - Batch processing with `ReceiveMessage` (up to 10 messages)

2. **Alert Correlation**
   ```python
   # Group related alerts before processing
   def correlate_alerts(alerts):
       # Group by resource, time window, alert type
       groups = defaultdict(list)
       for alert in alerts:
           key = (alert['resource'], alert['alert_type'])
           groups[key].append(alert)

       # Create single incident for correlated alerts
       return [create_incident(group) for group in groups.values()]
   ```

3. **Auto-scaling ECS Tasks**
   - Use target tracking scaling based on SQS queue depth
   - Scale from 0 to N tasks based on load
   - Target: Process each alert within 30 seconds

4. **Rate Limiting for LLM Calls**
   - Implement token bucket algorithm
   - Cache similar incidents (Redis)
   - Use Claude Haiku for low-priority alerts (faster, cheaper)

### 7.2 Error Handling & Retries

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_llm_with_retry(prompt, context):
    """Retry LLM calls with exponential backoff"""
    try:
        return bedrock_client.invoke_model(...)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise
```

**DLQ Strategy**:
- Failed alerts go to Dead Letter Queue
- Separate Lambda processes DLQ every 5 minutes
- Alert ops team if DLQ depth > 10

### 7.3 Cost Optimization

**Estimated Monthly Costs** (for 1000 incidents/month):

| Service | Usage | Cost |
|---------|-------|------|
| Bedrock (Claude 3.5 Sonnet) | 1000 incidents × 10K tokens | ~$30 |
| Bedrock (Claude 3 Haiku - low priority) | 500 incidents × 5K tokens | ~$2 |
| ECS Fargate | 2 vCPU, 4GB, 50 hours/month | ~$25 |
| DynamoDB | 1M reads, 100K writes | ~$1 |
| OpenSearch | t3.medium, 24/7 | ~$45 |
| S3 | 10GB storage, 1000 requests | ~$1 |
| CloudWatch | Logs, metrics | ~$10 |
| **Total** | | **~$114/month** |

**Optimization Strategies**:
1. Use Claude Haiku for low-severity alerts (10x cheaper)
2. Implement aggressive caching for similar incidents
3. Use OpenSearch free tier if possible
4. Archive old incidents to S3 Glacier after 30 days
5. Scale ECS to zero during low-alert periods

### 7.4 Multi-Region Considerations

For high-availability:

**Active-Passive Setup**:
```
Primary Region (us-east-1):
- All components active
- DynamoDB Global Tables replicate to us-west-2
- S3 Cross-Region Replication

Secondary Region (us-west-2):
- Read-only OpenSearch replica
- ECS tasks on standby
- Failover triggered by Route53 health checks
```

---

## 8. Security & Compliance

### 8.1 IAM Roles & Permissions

**ECS Task Role** (Principle of Least Privilege):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:StartQuery",
        "logs:GetQueryResults",
        "cloudwatch:GetMetricData",
        "xray:GetTraceSummaries",
        "xray:BatchGetTraces",
        "eks:DescribeCluster",
        "rds:DescribeDBInstances",
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/incident_state",
        "arn:aws:dynamodb:*:*:table/incident_history",
        "arn:aws:dynamodb:*:*:table/agent_memory"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::ai-incident-agent-artifacts/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
    }
  ]
}
```

### 8.2 Data Encryption

- **At Rest**:
  - DynamoDB: AWS-managed encryption
  - S3: SSE-S3 or SSE-KMS for sensitive data
  - OpenSearch: Encryption at rest enabled

- **In Transit**:
  - TLS 1.3 for all API calls
  - VPC endpoints for AWS service communication
  - Private subnets for ECS tasks (no public IPs)

### 8.3 PII Handling

**Log Redaction**:
```python
import re

def redact_sensitive_data(log_message):
    """Redact PII before sending to LLM"""
    # Email addresses
    log_message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                        '[EMAIL]', log_message)
    # IP addresses
    log_message = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
                        '[IP]', log_message)
    # Credit cards
    log_message = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                        '[CARD]', log_message)
    return log_message
```

### 8.4 Audit Logging

All agent actions logged to CloudWatch with:
- Incident ID
- LLM prompts and responses (sanitized)
- AWS API calls made
- Notifications sent
- Engineer feedback received

**Retention**: 90 days in CloudWatch, archived to S3 Glacier

---

## 9. Implementation Phases

### Phase 1: MVP (Weeks 1-2)
**Goal**: Prove core concept with minimal features

- ✅ Set up CloudWatch Alarm → EventBridge → Lambda flow
- ✅ Build basic LangGraph workflow (alert → analyze → notify)
- ✅ Integrate with Bedrock Claude 3.5 Sonnet
- ✅ Send enriched alerts to Slack
- ✅ Store incidents in DynamoDB

**Success Metric**: First AI-enriched alert sent to Slack

### Phase 2: Context Gathering (Weeks 3-4)
**Goal**: Add intelligent context collection

- ✅ Implement CloudWatch Logs Insights queries
- ✅ Fetch relevant metrics around alert time
- ✅ Query resource metadata via AWS APIs
- ✅ Enhance LLM prompts with gathered context

**Success Metric**: Incident analysis includes logs + metrics

### Phase 3: Memory & Learning (Weeks 5-6)
**Goal**: Enable agent to learn from past incidents

- ✅ Set up OpenSearch with k-NN for vector search
- ✅ Generate embeddings for incidents
- ✅ Implement similarity search for past incidents
- ✅ Add feedback collection via Slack buttons
- ✅ Store resolutions in incident_history

**Success Metric**: Agent suggests similar past incidents

### Phase 4: Runbook Integration (Weeks 7-8)
**Goal**: Match incidents to runbooks

- ✅ Create runbook library in S3 (markdown files)
- ✅ Generate embeddings for runbooks
- ✅ Implement semantic search for runbook matching
- ✅ Include runbook links in notifications

**Success Metric**: 80%+ of incidents matched to runbooks

### Phase 5: Production Hardening (Weeks 9-10)
**Goal**: Make it production-ready

- ✅ Implement error handling and retries
- ✅ Add auto-scaling for ECS tasks
- ✅ Set up monitoring and alerting for the agent itself
- ✅ Add PII redaction
- ✅ Implement cost optimization (caching, Haiku for low-priority)
- ✅ Create operational runbooks for the agent

**Success Metric**: 99.9% uptime, <30s p95 processing time

### Phase 6: Advanced Features (Weeks 11-12)
**Goal**: Enhance with advanced capabilities

- ✅ Multi-channel notifications (PagerDuty, MS Teams)
- ✅ Incident correlation (group related alerts)
- ✅ Auto-remediation for known issues (optional)
- ✅ Dashboard for agent performance metrics
- ✅ Fine-tuning based on feedback data

**Success Metric**: 50%+ MTTR reduction measured

---

## 10. Success Metrics & KPIs

### 10.1 Agent Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Alert Processing Time** | p95 < 30 seconds | CloudWatch metrics |
| **Context Gathering Success** | > 95% | DynamoDB state tracking |
| **LLM Call Success Rate** | > 99% | Error logs, retries |
| **Notification Delivery** | > 99.9% | Slack/PagerDuty APIs |
| **Agent Uptime** | 99.9% | ECS task health checks |

### 10.2 Business Impact Metrics

| Metric | Baseline | Target (3 months) |
|--------|----------|-------------------|
| **Mean Time to Acknowledge (MTTA)** | 15 min | 5 min (-67%) |
| **Mean Time to Resolution (MTTR)** | 120 min | 50 min (-58%) |
| **Alert Noise (false positives)** | 40% | 10% (-75%) |
| **On-call Escalations** | 30/month | 10/month (-67%) |
| **Engineer Satisfaction** | Baseline survey | +40% improvement |

### 10.3 Learning & Improvement Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Runbook Match Accuracy** | > 80% | Engineer feedback |
| **Root Cause Accuracy** | > 70% | Post-incident validation |
| **Recommendation Usefulness** | > 4/5 rating | Slack feedback buttons |
| **Incident Library Growth** | +100/month | DynamoDB count |
| **Pattern Recognition** | 50+ patterns learned | Agent memory table |

---

## 11. Monitoring the Agent Itself

**Meta-Observability**: The agent needs monitoring too!

```
CloudWatch Dashboard: "AI-Incident-Agent-Health"
├── ECS Task Health
│   ├── Running tasks count
│   ├── CPU/Memory utilization
│   └── Task failures
├── Queue Metrics
│   ├── SQS queue depth
│   ├── DLQ depth (alert if > 5)
│   └── Message age
├── Processing Metrics
│   ├── Alerts processed/hour
│   ├── Average processing time
│   └── LLM call latency
├── Error Metrics
│   ├── LLM call failures
│   ├── Context gathering failures
│   └── Notification delivery failures
└── Cost Metrics
    ├── Bedrock token usage
    └── Estimated monthly spend
```

**Alerts for the Agent**:
- SQS DLQ depth > 10 → Page ops team
- ECS task failures > 5 in 5 min → Investigate
- LLM error rate > 5% → Check Bedrock status
- Processing time p95 > 60s → Scale up tasks

---

## 12. Next Steps

### Immediate Actions
1. **Review & Approve Architecture** - Stakeholder sign-off
2. **Set Up AWS Environment** - Terraform workspace, IAM roles
3. **Prototype LangGraph Workflow** - Prove core concept
4. **Select LLM Provider** - Bedrock vs SageMaker decision
5. **Create Sample Runbooks** - At least 5 for MVP

### Week 1 Milestones
- [ ] CloudWatch → EventBridge → Lambda → SQS flow working
- [ ] LangGraph agent processes first alert end-to-end
- [ ] Slack notification sent with AI-generated summary
- [ ] DynamoDB tables created and tested

### Week 2 Milestones
- [ ] Context gathering (logs + metrics) functional
- [ ] LLM analysis includes gathered context
- [ ] Basic error handling and retries implemented
- [ ] Documentation for team handoff

---

**Document Version**: 1.0
**Author**: Prime Orchestrator + Solution Architect
**Status**: Architecture Design Complete ✅
**Next**: Implementation Phase
