"""SRE & AIOps Architecture"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda, ECS
from diagrams.aws.management import Cloudwatch, SystemsManager
from diagrams.aws.integration import SNS
from diagrams.aws.storage import S3
from diagrams.aws.database import DynamodbTable
from diagrams.aws.general import Users
from diagrams.onprem.monitoring import Datadog
from diagrams.onprem.iac import Terraform
from diagrams.onprem.ci import GithubActions
from diagrams.programming.language import Python

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.7",
    "ranksep": "1.0",
}

with Diagram(
    "SRE & AIOps Architecture",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/04_sre_aiops",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
):
    with Cluster("Monitoring Sources"):
        cw = Cloudwatch("CloudWatch\nMetrics & Logs")
        app_logs = ECS("Application\nServices")
        argocd = GithubActions("ArgoCD\nDeploy Events")

    with Cluster("Datadog Platform (Existing + Bits AI)"):
        dd_ingest = Datadog("Datadog Agent\nMetrics/Logs/Traces")

        with Cluster("Bits AI SRE (Enable Day 1)"):
            triage = Datadog("Auto Triage\nSeverity Classification")
            correlate = Datadog("Alert Correlation\n-60-80% Noise")
            rca = Datadog("Root Cause\nAnalysis")
            predict = Datadog("Predictive\nAlerting")

    with Cluster("Custom LangGraph Incident Agent (Phase 2)"):
        agent = Python("LangGraph Agent\nFinancial-Specific\nTriage")
        runbooks = S3("Runbook\nLibrary")
        history = DynamodbTable("Incident\nHistory DB")

    with Cluster("Automation Risk Levels"):
        with Cluster("Level 0-1: Auto (No Approval)"):
            auto = Lambda("Context Gather\nAlert Enrich\nRCA Generate")

        with Cluster("Level 2: Policy-Based"):
            policy = Lambda("Auto-Close P4\nScale Read Replicas\n(Pre-Approved)")

        with Cluster("Level 3-5: Human Required"):
            approval = SNS("Approval Request")
            engineer = Users("On-Call Engineer")
            ssm = SystemsManager("SSM\nRunbook Execution")

    with Cluster("Audit & Compliance (SOC 2 CC8.1)"):
        audit = S3("S3 Object Lock\nDecision Audit Trail")
        dynamo_audit = DynamodbTable("Remediation Log\nWho/What/When")

    # Monitoring flow
    app_logs >> cw >> dd_ingest
    argocd >> dd_ingest

    dd_ingest >> triage >> correlate
    correlate >> rca
    correlate >> predict

    # LangGraph agent
    rca >> agent
    agent >> runbooks
    agent >> history

    # Automation levels
    agent >> auto
    agent >> policy
    agent >> Edge(label="High Risk", color="red") >> approval >> engineer
    engineer >> ssm

    # Audit
    auto >> audit
    policy >> dynamo_audit
    ssm >> dynamo_audit
