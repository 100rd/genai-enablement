"""Overall AI Platform Architecture for Financial Services"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.ml import Sagemaker, SagemakerModel, SagemakerNotebook
from diagrams.aws.ml import Textract, Comprehend
from diagrams.aws.database import Neptune, DynamodbTable
from diagrams.aws.integration import Eventbridge, StepFunctions, SNS, SQS
from diagrams.aws.compute import Lambda
from diagrams.aws.storage import S3
from diagrams.aws.security import IAM, SecretsManager, KMS
from diagrams.aws.management import Cloudwatch, Cloudtrail
from diagrams.aws.network import VPC, PrivateSubnet, ELB
from diagrams.aws.general import Users
from diagrams.onprem.monitoring import Datadog
from diagrams.onprem.vcs import Gitlab
from diagrams.onprem.ci import GithubActions
from diagrams.generic.device import Mobile

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.8",
    "ranksep": "1.2",
}

with Diagram(
    "AI Enablement Platform - Financial Services",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/01_overall_platform",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
):
    users = Users("Analysts & Engineers")

    with Cluster("AWS Cloud (SOC 2 / ISO 27001)"):
        with Cluster("VPC - Private Subnets"):
            with Cluster("Workstream 1: KYC/KYB & Transaction Monitoring"):
                textract = Textract("Textract\nDocument OCR")
                bedrock = SagemakerModel("Bedrock\nClaude LLM")
                sagemaker = Sagemaker("SageMaker\nFraud/AML Models")
                neptune = Neptune("Neptune\nGraph DB / GNN")

            with Cluster("Workstream 2: SRE & AIOps"):
                cw = Cloudwatch("CloudWatch\nMetrics & Logs")
                datadog = Datadog("Datadog\nBits AI SRE")
                lambda_fn = Lambda("Lambda\nIncident Agent")

            with Cluster("Workstream 3: Code Gen & Delivery"):
                gitlab = Gitlab("GitLab CI\n+ Duo AI")
                # Using GithubActions as proxy for ArgoCD icon
                argocd = GithubActions("ArgoCD\nDeployment")

        with Cluster("Data & Orchestration"):
            s3 = S3("S3\nDocuments & Models")
            dynamo = DynamodbTable("DynamoDB\nDecisions & Audit")
            eventbridge = Eventbridge("EventBridge")
            step_fn = StepFunctions("Step Functions\nOrchestration")
            sns = SNS("SNS\nAlerts")

        with Cluster("Security & Compliance (SR 11-7)"):
            iam = IAM("IAM\nLeast Privilege")
            kms = KMS("KMS\nEncryption")
            cloudtrail = Cloudtrail("CloudTrail\nAudit Trail")
            secrets = SecretsManager("Secrets Manager")

    # Data flows
    users >> Edge(label="KYC Docs") >> s3
    s3 >> eventbridge >> step_fn

    step_fn >> textract
    step_fn >> bedrock
    textract >> dynamo
    bedrock >> dynamo

    s3 >> sagemaker
    sagemaker >> neptune
    neptune >> dynamo
    dynamo >> sns >> users

    # SRE flows
    cw >> datadog
    datadog >> lambda_fn
    lambda_fn >> sns

    # Compliance
    cloudtrail >> s3
    iam >> kms
