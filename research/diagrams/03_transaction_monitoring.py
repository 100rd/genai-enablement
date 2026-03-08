"""Transaction Monitoring AI Architecture"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.ml import Sagemaker, SagemakerModel
from diagrams.aws.database import Neptune, DynamodbTable, ElastiCache
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.compute import Lambda
from diagrams.aws.storage import S3
from diagrams.aws.analytics import KinesisDataStreams, KinesisDataFirehose
from diagrams.aws.management import Cloudwatch
from diagrams.aws.general import Users

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.8",
    "nodesep": "0.7",
    "ranksep": "1.0",
}

with Diagram(
    "Transaction Monitoring AI Architecture",
    filename="/Users/lo/Develop/multi-team-agentic/project/genai-enablement/research/diagrams/03_transaction_monitoring",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    txn = Users("Transaction\nStream\n100K-1M/day")

    with Cluster("Real-Time Path (<100ms)"):
        kinesis = KinesisDataStreams("Kinesis\nData Stream")

        with Cluster("Parallel Scoring"):
            ml_score = Sagemaker("SageMaker\nEndpoint\n(XGBoost)")
            rule_engine = Lambda("Rule Engine\n(Lambda)\nExisting Rules")
            cache = ElastiCache("ElastiCache\nCustomer Profiles")

        combine = Lambda("Score\nCombiner\n(Weighted)")

    with Cluster("Near Real-Time Path (Minutes)"):
        firehose = KinesisDataFirehose("Firehose\nBatch Buffer")
        neptune = Neptune("Neptune\nGNN Analysis\nNetwork Patterns")
        sagemaker_batch = Sagemaker("SageMaker\nBatch Transform\n(GNN Inference)")

    with Cluster("Alert Management"):
        dynamo = DynamodbTable("DynamoDB\nAlert Store")
        bedrock = SagemakerModel("Bedrock Claude\nAlert Enrichment\n& Summarization")
        sns_high = SNS("P1 Alert\nImmediate Review")
        sqs_low = SQS("P2-P4 Queue\nBatch Review")

    with Cluster("Analyst Review"):
        analyst = Users("AML Analyst\nHuman Decision")
        s3_sar = S3("SAR Filing\nDocumentation")

    with Cluster("Model Monitoring (SR 11-7)"):
        cw = Cloudwatch("CloudWatch\nModel Metrics")
        drift = Lambda("Drift Detection\n(SageMaker Monitor)")
        s3_models = S3("Model Registry\nVersioned Artifacts")

    # Real-time flow
    txn >> kinesis
    kinesis >> ml_score
    kinesis >> rule_engine
    kinesis >> cache
    ml_score >> combine
    rule_engine >> combine
    cache >> ml_score

    # Near real-time
    kinesis >> firehose >> neptune
    neptune >> sagemaker_batch
    sagemaker_batch >> dynamo

    # Alert flow
    combine >> dynamo
    dynamo >> bedrock
    bedrock >> Edge(label="High Risk", color="red") >> sns_high >> analyst
    bedrock >> Edge(label="Low/Med Risk", color="blue") >> sqs_low >> analyst
    analyst >> s3_sar

    # Monitoring
    ml_score >> cw
    cw >> drift
    drift >> s3_models
