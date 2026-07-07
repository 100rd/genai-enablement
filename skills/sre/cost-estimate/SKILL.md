---
name: cost-estimate
description: Estimate infrastructure costs before applying Terraform changes. Requires human approval for changes exceeding thresholds. Runs in a forked context (infracost JSON stays out of the caller's window). Args arrive in $ARGUMENTS, e.g. "./infrastructure/prod --threshold 500".
model: sonnet
context: fork
user-invocable: true
# platform extension namespace (in-house skill moved into registry — see REGISTRY origin):
version: 0.1.0
tags: [sre, terraform, cost, infracost]
compatible_tools: [claude-code, multiqlti, omnius, cursor, antigravity]
tier: T1
license: MIT
---

# Cost Estimation Skill

Estimate infrastructure costs before applying Terraform/Terragrunt changes. This skill acts as a gate to prevent unexpectedly expensive deployments.

## Prerequisites

- `infracost` CLI installed: https://www.infracost.io/docs/
- INFRACOST_API_KEY set in environment

## Arguments
- `path`: Path to Terraform/Terragrunt directory (default: current directory)
- `--threshold <amount>`: Monthly cost threshold requiring approval (default: $100)
- `--currency`: Currency for display (default: USD)

## Workflow

### Step 1: Check for Infracost

```bash
if ! command -v infracost &> /dev/null; then
  echo "❌ infracost CLI not found. Install from https://www.infracost.io/docs/"
  echo "   brew install infracost"
  exit 1
fi
```

### Step 2: Run Cost Breakdown

For Terraform:
```bash
infracost breakdown --path "$PATH" --format json > /tmp/infracost-report.json
```

For Terragrunt:
```bash
infracost breakdown --path "$PATH" --terragrunt --format json > /tmp/infracost-report.json
```

### Step 3: Parse Results

```bash
# Extract key metrics
MONTHLY_COST=$(jq -r '.totalMonthlyCost' /tmp/infracost-report.json)
PREVIOUS_COST=$(jq -r '.pastTotalMonthlyCost // 0' /tmp/infracost-report.json)
DIFF_COST=$(jq -r '.diffTotalMonthlyCost // 0' /tmp/infracost-report.json)

echo "📊 Cost Estimate:"
echo "   Current monthly: \$$PREVIOUS_COST"
echo "   After changes:   \$$MONTHLY_COST"
echo "   Difference:      \$$DIFF_COST"
```

### Step 4: Generate Report

```markdown
# Infrastructure Cost Estimate

**Path**: [terraform-path]
**Timestamp**: [ISO timestamp]

## Cost Summary

| Metric | Amount |
|--------|--------|
| Current Monthly Cost | $X.XX |
| Projected Monthly Cost | $Y.YY |
| Monthly Difference | $Z.ZZ |
| Annual Impact | $W.WW |

## Resource Breakdown

| Resource | Type | Monthly Cost | Change |
|----------|------|--------------|--------|
| aws_instance.app | m5.large | $70.00 | +$70.00 |
| aws_rds_instance.db | db.r5.large | $150.00 | $0.00 |
| ... | ... | ... | ... |

## Cost Drivers

1. **Highest Cost**: [resource] - $X/month
2. **Biggest Increase**: [resource] - +$Y/month
3. **New Resources**: X resources adding $Z/month

## Recommendations

- [Cost optimization suggestions]
```

### Step 5: Threshold Check

```bash
THRESHOLD=${THRESHOLD:-100}

if (( $(echo "$DIFF_COST > $THRESHOLD" | bc -l) )); then
  echo ""
  echo "⚠️ COST THRESHOLD EXCEEDED"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Monthly increase: \$$DIFF_COST"
  echo "Threshold: \$$THRESHOLD"
  echo ""
  echo "This change requires human approval before proceeding."
  echo ""
  # Return non-zero to indicate approval needed
  exit 2
fi

if (( $(echo "$DIFF_COST < -$THRESHOLD" | bc -l) )); then
  echo ""
  echo "💰 COST SAVINGS DETECTED"
  echo "Monthly savings: \$$DIFF_COST"
fi
```

### Step 6: Log to History

If costs are significant, record the estimate in the consuming runtime's run/audit log:

```markdown
## [TIMESTAMP] cost-estimate: Infrastructure Cost Analysis

**Action**: validation
**Category**: infrastructure

### Cost Summary
- Current: $X/month
- Projected: $Y/month
- Change: $Z/month

### Threshold Status
[PASSED/EXCEEDED]

### Approval
[Required/Not Required]

**Tags**: #cost #infrastructure #terraform
```

## Approval Flow

When threshold is exceeded:

1. Display detailed cost breakdown
2. Show which resources are driving costs
3. Provide optimization recommendations
4. **REQUIRE explicit user approval**:
   ```
   ⚠️ CRITICAL DECISION: Infrastructure Cost Increase
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   What: Terraform apply will increase monthly costs by $X
   Why: [New resources / Upgraded instances / etc.]
   Risk: Unexpected billing increase

   Do you approve? (y/n):
   ```

## Cost Optimization Suggestions

The skill should also provide recommendations:

### Compute
- Consider spot/preemptible instances for non-critical workloads
- Right-size instances based on actual usage
- Use reserved instances for predictable workloads

### Storage
- Use appropriate storage classes (S3 Intelligent-Tiering)
- Enable lifecycle policies for old data
- Consider cheaper storage for backups

### Database
- Use Aurora Serverless for variable workloads
- Consider read replicas vs larger instances
- Review backup retention periods

### Network
- Minimize cross-AZ data transfer
- Use VPC endpoints for AWS services
- Review NAT Gateway usage

## Integration with Terraform Workflow

This skill should be called:
1. After `terraform plan`
2. Before `terraform apply`
3. As part of PR review for infrastructure changes

## Example Usage

```bash
/cost-estimate ./infrastructure/prod
/cost-estimate ./infrastructure/prod --threshold 500
/cost-estimate . --currency EUR
```
