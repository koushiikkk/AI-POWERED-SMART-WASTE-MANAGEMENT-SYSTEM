---
name: Cloud
description: Rules for optional cloud integration.
---

AWS is optional/demo-only.

Possible conceptual architecture:

Frontend:
S3 + CloudFront

Backend:
EC2 / ECS / App Runner

Database:
RDS MySQL

Monitoring:
CloudWatch

Security:
IAM

Networking:
VPC + Security Groups

Rules:

- verify current AWS service/free-tier information before claiming anything
- never claim a service is free without verification
- never deploy cloud infrastructure if it threatens the exam MVP
- local MySQL remains the safe exam default
- clearly distinguish conceptual, configured, tested, and deployed cloud status
- never hardcode cloud credentials
