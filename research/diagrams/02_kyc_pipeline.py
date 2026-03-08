"""KYC/KYB AI Pipeline Architecture"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.ml import Sagemaker, SagemakerModel
from diagrams.aws.ml import Textract
from diagrams.aws.database import Neptune, DynamodbTable
from diagrams.aws.integration import Eventbridge, StepFunctions, SNS
from diagrams.aws.compute import Lambda
from diagrams.aws.storage import S3
from diagrams.aws.analytics import KinesisDataStreams
from diagrams.aws.security import IAM
from diagrams.aws.management import Cloudtrail
from diagrams.aws.general import Users

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.7",
    "ranksep": "1.0",
}

with Diagram(
    "KYC/KYB AI Pipeline",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/02_kyc_pipeline",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    customer = Users("Customer\nDocuments")

    with Cluster("Document Intake"):
        s3_upload = S3("S3 Upload\nBucket")
        eb = Eventbridge("EventBridge\nTrigger")

    with Cluster("Step Functions Orchestration"):
        sf = StepFunctions("Orchestrator")

        with Cluster("Document Processing"):
            textract_id = Textract("Textract\nAnalyzeID\n(Passports, IDs)")
            textract_doc = Textract("Textract\nAnalyzeDocument\n(Bank Statements)")
            bedrock = SagemakerModel("Bedrock Claude\nUnstructured Docs\n(Legal, Contracts)")

        with Cluster("Entity Resolution"):
            entity_res = Lambda("AWS Entity\nResolution\n(Fuzzy Matching)")
            neptune = Neptune("Neptune\nOwnership Graph\n(UBO Chains)")

        with Cluster("Risk Assessment"):
            sagemaker = Sagemaker("SageMaker\nRisk Scoring\n(XGBoost + SHAP)")
            sanctions = Lambda("Sanctions/PEP\nScreening\n(Real-time)")

    with Cluster("Decision & Audit"):
        dynamo = DynamodbTable("DynamoDB\nDecision Store")
        s3_audit = S3("S3 Object Lock\nAudit Archive")
        cloudtrail = Cloudtrail("CloudTrail\nCompliance Log")

    with Cluster("Human Review"):
        sns = SNS("SNS Alert\n(Low Confidence)")
        analyst = Users("KYC Analyst\nHuman-in-Loop")

    # Flow
    customer >> s3_upload >> eb >> sf

    sf >> textract_id
    sf >> textract_doc
    sf >> bedrock

    textract_id >> entity_res
    textract_doc >> entity_res
    bedrock >> entity_res

    entity_res >> neptune
    neptune >> sagemaker
    sagemaker >> sanctions

    sanctions >> dynamo
    dynamo >> s3_audit
    dynamo >> cloudtrail

    sagemaker >> Edge(label="Score < 0.7", color="orange") >> sns >> analyst
    analyst >> Edge(label="Approve/Reject") >> dynamo
