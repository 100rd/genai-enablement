---
name: blast-radius
description: Analyze the blast radius and impact of Terraform changes before applying. Identifies affected resources, downstream dependencies, and potential risks.
model: sonnet
context: fork
user-invocable: true
# platform extension namespace (in-house skill moved into registry — see REGISTRY origin):
version: 0.1.0
tags: [sre, terraform, risk, change-analysis]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T1
license: MIT
---

# Blast Radius Analysis

Analyze the potential impact of Terraform/Terragrunt changes at `$ARGUMENTS` before applying them.

## Steps

1. **Generate plan**: Run `terraform plan -out=plan.tfplan` and `terraform show -json plan.tfplan > plan.json`
2. **Extract changes**: Parse plan JSON for creates, updates, deletes, replaces
3. **Identify high-risk**: Flag changes to databases, VPCs, IAM, security groups, EKS, RDS
4. **Analyze dependencies**: Run `terraform graph` and trace upstream/downstream impact
5. **Generate report**: Produce blast radius report with risk classification and rollback plan
6. **Approval gate**: If blast radius is high (16+ changes, database changes, or IAM changes), require human approval

## Risk Thresholds

| Metric | Low | Medium | High | Critical |
|--------|-----|--------|------|----------|
| Total changes | 1-5 | 6-15 | 16-30 | 30+ |
| Deletes/Replaces | 0 | 1-3 | 4-10 | 10+ |
| Database changes | 0 | 0 | 1 | 2+ |
| Network changes | 0-2 | 3-5 | 6-10 | 10+ |
| IAM changes | 0-3 | 4-10 | 11-20 | 20+ |

## High-Risk Resource Types

aws_db_instance, aws_rds_cluster, aws_elasticache_cluster, aws_iam_role, aws_iam_policy, aws_security_group, aws_vpc, aws_subnet, aws_route_table, aws_nat_gateway, aws_internet_gateway, aws_lb, aws_autoscaling_group, aws_ecs_service, aws_eks_cluster, aws_lambda_function

## Output

Generate a structured report with:
- Executive summary (change counts by action type)
- Risk classification (critical/high/medium/low)
- Dependency analysis (upstream and downstream)
- Detailed change analysis per resource
- Rollback plan
- Pre-apply checklist

Call this before any `terraform apply`, during PR review for infrastructure changes, and before production deployments.
