"""Phased Implementation Roadmap"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.ml import Sagemaker, SagemakerModel, Textract
from diagrams.aws.database import Neptune
from diagrams.aws.compute import Lambda
from diagrams.aws.general import Users
from diagrams.onprem.monitoring import Datadog
from diagrams.onprem.vcs import Gitlab, Github
from diagrams.onprem.ci import GithubActions
from diagrams.programming.language import Python

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "1.0",
    "nodesep": "0.5",
    "ranksep": "1.5",
}

with Diagram(
    "AI Enablement Phased Roadmap",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/07_phased_roadmap",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    with Cluster("Phase 1: Foundation\nMonths 1-3 | ~$20K/mo"):
        p1_dd = Datadog("Enable\nDatadog Bits AI")
        p1_copilot = Github("GitHub Copilot\n10 Dev Pilot")
        p1_textract = Textract("Textract\nKYC OCR")
        p1_gov = Users("AI Governance\nCommittee")

    with Cluster("Phase 2: Core Adoption\nMonths 3-6 | ~$55K/mo"):
        p2_sm = Sagemaker("SageMaker\nFraud/AML Models")
        p2_bedrock = SagemakerModel("Bedrock Claude\nDoc Analysis")
        p2_copilot = Github("Copilot\nAll Devs")
        p2_gitlab = Gitlab("GitLab Duo\nCI/CD AI")

    with Cluster("Phase 3: Advanced\nMonths 6-12 | ~$90K/mo"):
        p3_neptune = Neptune("Neptune GNN\nAML Network")
        p3_agent = Python("LangGraph\nIncident Agent")
        p3_argocd = GithubActions("AI-Enhanced\nArgoCD")

    with Cluster("Phase 4: Scale\nMonths 12-18 | ~$120K/mo"):
        p4_scale = Users("All Business\nLines")
        p4_cert = Users("ISO 42001\nCertification")
        p4_playbooks = Users("AI Playbook\nLibrary")

    # Phase connections
    p1_dd >> Edge(label="25% MTTR reduction", color="blue") >> p2_sm
    p1_copilot >> Edge(label="30% dev productivity", color="green") >> p2_copilot
    p1_textract >> Edge(label="65% faster OCR", color="purple") >> p2_bedrock
    p1_gov >> Edge(label="SR 11-7 framework", color="orange") >> p2_sm

    p2_sm >> Edge(label="60% fewer false positives", color="blue") >> p3_neptune
    p2_bedrock >> Edge(color="purple") >> p3_neptune
    p2_copilot >> Edge(color="green") >> p3_argocd
    p2_gitlab >> Edge(color="green") >> p3_argocd

    p3_neptune >> Edge(label="80% fewer false positives", color="blue") >> p4_scale
    p3_agent >> Edge(label="75% MTTR reduction", color="blue") >> p4_scale
    p3_argocd >> Edge(color="green") >> p4_scale
    p4_scale >> p4_cert
    p4_scale >> p4_playbooks
