"""Compliance & Governance Framework"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.security import IAM, KMS, Inspector
from diagrams.aws.management import Cloudtrail, Config, Organizations
from diagrams.aws.ml import Sagemaker, SagemakerModel
from diagrams.aws.storage import S3
from diagrams.aws.database import DynamodbTable
from diagrams.aws.general import Users, GenericDatabase
from diagrams.aws.compute import Lambda

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.7",
    "ranksep": "1.0",
}

with Diagram(
    "AI Governance & Compliance Framework (SR 11-7)",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/06_compliance_governance",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
):
    with Cluster("AI Governance Committee"):
        committee = Users("AI Governance\nCommittee")
        risk_owner = Users("Model Risk\nOwner")
        validator = Users("Independent\nValidator")

    with Cluster("Model Lifecycle (SR 11-7 Compliant)"):
        with Cluster("1. Development"):
            notebook = Sagemaker("SageMaker\nNotebook\n(Training)")
            data = S3("Training Data\n(Classified)")
            registry = Sagemaker("Model Registry\n(Versioned)")

        with Cluster("2. Validation"):
            val_test = Lambda("Automated\nValidation\n(Accuracy, Bias)")
            explainability = SagemakerModel("SageMaker\nClarify\n(SHAP)")
            review_doc = DynamodbTable("Validation\nReport")

        with Cluster("3. Deployment"):
            canary = Lambda("Canary\nDeployment")
            shadow = Lambda("Shadow Mode\n(A/B Test)")
            prod = Sagemaker("Production\nEndpoint")

        with Cluster("4. Monitoring"):
            drift = Lambda("Data Drift\nDetection")
            perf = Lambda("Performance\nMonitoring")
            bias_mon = Lambda("Bias\nMonitoring")

    with Cluster("Compliance Controls"):
        with Cluster("SOC 2"):
            cc6 = IAM("CC6: Access\nControl (IAM)")
            cc7 = Config("CC7: System\nOps (Monitoring)")
            cc8 = Organizations("CC8: Change\nMgmt (Registry)")

        with Cluster("ISO 27001"):
            kms_ctrl = KMS("A.10: Crypto\n(KMS/BYOK)")
            audit = Cloudtrail("A.12: Ops\nSecurity (Logs)")

        with Cluster("Audit Trail (Immutable)"):
            ct = Cloudtrail("CloudTrail\nAll API Calls")
            s3_lock = S3("S3 Object Lock\n7yr Retention")
            audit_db = DynamodbTable("Decision Log\nEvery Inference")

    # Governance flow
    committee >> risk_owner >> validator

    # Lifecycle
    notebook >> data
    data >> registry
    registry >> val_test
    val_test >> explainability
    explainability >> review_doc
    review_doc >> Edge(label="Approved", color="green") >> canary
    canary >> shadow >> prod

    # Monitoring
    prod >> drift
    prod >> perf
    prod >> bias_mon
    drift >> Edge(label="Drift Detected", color="orange") >> registry

    # Compliance
    prod >> ct >> s3_lock
    prod >> audit_db
    cc6 >> prod
    cc8 >> registry

    # Validator reviews
    validator >> review_doc
