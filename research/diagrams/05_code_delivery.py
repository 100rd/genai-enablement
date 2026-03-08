"""Code Generation & Software Delivery Pipeline"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.ml import SagemakerModel
from diagrams.aws.compute import ECS, EKS
from diagrams.aws.devtools import Codebuild
from diagrams.aws.general import Users
from diagrams.onprem.vcs import Gitlab, Github
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.security import Vault
from diagrams.programming.language import Go, Rust, Nodejs
from diagrams.onprem.monitoring import Datadog

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.6",
    "ranksep": "1.0",
}

with Diagram(
    "AI-Enhanced Software Delivery Pipeline",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/05_code_delivery",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    dev = Users("Developer")

    with Cluster("AI Code Generation"):
        copilot = Github("GitHub Copilot\nEnterprise")
        with Cluster("Language Support"):
            rust = Rust("Rust")
            go = Go("Go")
            node = Nodejs("Node.js")

    with Cluster("GitLab CI Pipeline (+ Duo AI)"):
        gitlab = Gitlab("GitLab Repo\n+ MR Review AI")

        with Cluster("CI Stages"):
            lint = Codebuild("Lint &\nFormat")
            test = Codebuild("Test\n(AI-Generated)")
            security = Vault("Snyk + Checkov\nSAST/SCA/IaC")
            build = Codebuild("Build &\nContainer")

        with Cluster("AI Quality Gates"):
            risk = SagemakerModel("Deployment\nRisk Score")
            review = SagemakerModel("AI Code\nReview")

    with Cluster("ArgoCD Deployment"):
        argocd = GithubActions("ArgoCD\nGitOps Sync")

        with Cluster("Environments"):
            dev_env = EKS("Dev\n(Auto-Deploy)")
            staging = EKS("Staging\n(Auto-Deploy)")
            prod = ECS("Production\n(Manual Gate)")

    with Cluster("Observability"):
        dd = Datadog("Datadog\nDeploy Tracking\nDORA Metrics")

    # Dev flow
    dev >> copilot
    copilot >> rust
    copilot >> go
    copilot >> node

    rust >> gitlab
    go >> gitlab
    node >> gitlab

    # CI pipeline
    gitlab >> lint >> test >> security >> build
    gitlab >> review
    build >> risk

    # Deploy
    risk >> Edge(label="Low Risk", color="green") >> argocd
    risk >> Edge(label="High Risk", color="red") >> gitlab

    argocd >> dev_env >> staging >> prod

    # Monitoring
    prod >> dd
    staging >> dd
