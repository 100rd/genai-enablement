# Team Readiness Assessment Checklist

## DevOps Maturity

### CI/CD
- [ ] Automated build pipeline exists
- [ ] Automated test suite runs on PR
- [ ] Deployment is automated (not manual)
- [ ] Rollback process is documented
- [ ] Pipeline-as-code (not UI-configured)

### Infrastructure
- [ ] Infrastructure is codified (Terraform/CloudFormation/Pulumi)
- [ ] Environment parity (dev matches prod)
- [ ] Secrets management in place
- [ ] Resource tagging standards exist

### Observability
- [ ] Centralized logging
- [ ] Application metrics collected
- [ ] Alerting configured with escalation
- [ ] Dashboards for key services
- [ ] SLOs/SLIs defined

### Incident Management
- [ ] On-call rotation established
- [ ] Incident response process documented
- [ ] Runbooks exist for common incidents
- [ ] Post-incident reviews conducted
- [ ] Incident communication channels defined

## AI Readiness

### Technical
- [ ] Team has access to AI coding tools
- [ ] API access to LLM providers (if needed)
- [ ] Data can be shared with AI tools (no compliance blockers)
- [ ] Integration points identified (APIs, webhooks, pipelines)

### Organizational
- [ ] Management buy-in for AI adoption
- [ ] Team is willing to experiment
- [ ] Time allocated for learning/adoption
- [ ] Success metrics agreed upon
- [ ] Security/compliance review completed

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data privacy concerns | | | |
| Team resistance to change | | | |
| Tool vendor lock-in | | | |
| AI hallucination in production | | | |
| Cost overruns | | | |

## Recommendation

### Readiness Score: ___/20 (count checked items above)

| Score | Readiness | Recommendation |
|-------|-----------|----------------|
| 16-20 | High | Full engagement, start with Phase 2 |
| 11-15 | Medium | Start with Phase 1 foundation |
| 6-10 | Low | Focus on DevOps maturity first |
| 0-5 | Not Ready | Defer AI adoption, address basics |
