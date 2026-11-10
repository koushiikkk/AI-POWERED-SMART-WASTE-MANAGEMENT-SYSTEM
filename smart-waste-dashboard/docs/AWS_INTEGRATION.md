# AWS Cloud Services Integration Guide — CSPM Dustbin Level Detection

This document outlines the AWS cloud services architecture integrated into the **CSPM Smart Waste Management / Dustbin Level Detection System**.

---

## 1. System Architecture

```
                       Citizen Waste Report
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [Primary Workflow]             [AWS Secondary Copy]
       Supabase Storage               Amazon S3 Bucket
       (waste-reports)                (cspm-dustbin-images-koushik-2026)
               │                               │
               ▼                               │
      FastAPI / NVIDIA NIM                     │
      AI Level & Severity                      │
               │                               │
               ├───────────────────────────────┤
               ▼                               ▼
       Supabase PostgreSQL            Amazon DynamoDB
       (locations, reports,           (CSPM-Dustbin-Detections)
        collections)                  Latest state per bin_id
               │                               │
               ▼                               ▼
      Dashboard & Routes              Amazon SNS
                                      (CSPM-Dustbin-Alerts)
                                      Critical email alerts
                                               │
                                               ▼
                                      Amazon CloudWatch Logs
                                      (CSPM-Dustbin-Application-Logs)
```

---

## 2. Integrated AWS Services

### A. Amazon S3 (Image Archival)
- **Bucket:** `cspm-dustbin-images-koushik-2026`
- **Region:** `us-east-1`
- **Role:** Non-blocking archive copy of citizen-reported dustbin images.
- **Key Schema:** `bins/bin-{bin_id}/{YYYY}/{MM}/{DD}/{unique_token}_{filename}`
- **Security:** Private bucket. No public ACLs applied. Supabase storage remains primary for UI image rendering.

### B. Amazon DynamoDB (Detection State Cache)
- **Table:** `CSPM-Dustbin-Detections`
- **Partition Key:** `bin_id` (String)
- **Role:** Synchronizes the latest AI detection status per bin.
- **Attributes:**
  - `bin_id` (String)
  - `fill_level` (Number/Decimal)
  - `waste_status` (String: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - `latitude` (Number/Decimal)
  - `longitude` (Number/Decimal)
  - `detection_timestamp` (ISO 8601 String)
  - `detection timestamp` (ISO 8601 String)
  - `s3_object_key` (String, where available)
  - `confidence` (Number/Decimal)
  - `report_id` (Number)
  - `last_updated` (ISO 8601 String)
- **Behavior:** Overwrites item on each sync to maintain the latest status per bin.

### C. Amazon SNS (Urgent Alert Notifications)
- **Topic:** `CSPM-Dustbin-Alerts`
- **Topic ARN:** `arn:aws:sns:us-east-1:639677332609:CSPM-Dustbin-Alerts`
- **Role:** Email alert dispatch when a dustbin reaches `CRITICAL` status.
- **State-Transition Deduplication:**
  - Alerts trigger only when transitioning to `CRITICAL`.
  - Repeated alerts for unchanged `CRITICAL` states within the cooldown window (default 3600 seconds) are suppressed.
  - Non-critical detections (`LOW`, `MEDIUM`, `HIGH`) never send notifications.

### D. Amazon CloudWatch Logs (Application Auditing)
- **Log Group:** `CSPM-Dustbin-Application-Logs`
- **Log Stream:** `app-events`
- **Retention:** 1 day
- **Logged Events:**
  - `S3_IMAGE_UPLOADED`
  - `AI_DETECTION_COMPLETED`
  - `DYNAMODB_SYNC_SUCCESS` / `DYNAMODB_SYNC_FAILED`
  - `SNS_CRITICAL_ALERT_PUBLISHED`
  - `AWS_INTEGRATION_ERROR`
- **Sanitization:** Passwords, bearer tokens, API keys, credentials, and image bytes are redacted automatically before transmission.

---

## 3. Pending / Future Integrations

### Amazon API Gateway (`CSPM-Dustbin-API`)
- **Status:** Created in AWS without routes or active integrations.
- **Design Plan:**
  - Expose FastAPI REST endpoints using an HTTP API (API Gateway v2) HTTP Proxy integration (`ANY /{proxy+}`).
  - Maintain CORS origin matching frontend domain.
  - Keep existing frontend URLs pointed to direct backend until API Gateway routes and DNS mapping are finalized.

### AWS Lambda
- **Status:** Deferred due to AWS Academy IAM role restrictions (`iam:CreateRole` blocked).
- **Design Plan:**
  - Wrap FastAPI with `mangum` to execute as a serverless ASGI handler behind API Gateway.
  - Alternatively, use S3 `ObjectCreated` triggers to invoke an asynchronous vision analysis worker Lambda function.

---

## 4. Environment Configuration

```env
# AWS Region
AWS_REGION=us-east-1
AWS_DEFAULT_REGION=us-east-1

# AWS Credentials (Standard Boto3 Chain & AWS Academy Session Token)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=

# Feature Flags
AWS_ENABLED=true
AWS_S3_ENABLED=true
AWS_DYNAMODB_ENABLED=true
AWS_SNS_ENABLED=true
AWS_CLOUDWATCH_ENABLED=true

# Resource Names
AWS_S3_BUCKET=cspm-dustbin-images-koushik-2026
AWS_DYNAMODB_TABLE=CSPM-Dustbin-Detections
AWS_SNS_TOPIC_NAME=CSPM-Dustbin-Alerts
AWS_SNS_TOPIC_ARN=arn:aws:sns:us-east-1:639677332609:CSPM-Dustbin-Alerts
AWS_CLOUDWATCH_LOG_GROUP=CSPM-Dustbin-Application-Logs
AWS_CLOUDWATCH_LOG_STREAM=app-events
AWS_SNS_ALERT_COOLDOWN_SECONDS=3600
```

---

## 5. Verification Commands

```powershell
# 1. Run automated unit/mock test suite
smart-waste-dashboard\backend\.venv311\Scripts\python.exe -m pytest smart-waste-dashboard\tests\test_aws_services.py -v

# 2. Check live STS identity & resource connectivity
smart-waste-dashboard\backend\.venv311\Scripts\python.exe smart-waste-dashboard\backend\validate_aws_resources.py

# 3. Perform live end-to-end AWS integration check
smart-waste-dashboard\backend\.venv311\Scripts\python.exe smart-waste-dashboard\backend\test_real_aws_services.py
```

