"""
AWS Cloud Services Integration Module for CSPM Dustbin Level Detection.

Integrates:
- Amazon S3: Optional archival copies of dustbin images.
- Amazon DynamoDB: Synchronization of latest detection data per bin.
- Amazon SNS: Critical overflow email alerts (with deduplication).
- Amazon CloudWatch: Application audit logging for key system events.

Security & Design:
- Uses standard boto3 credential provider chain and supports AWS Academy temporary session credentials.
- Individual feature flags for granular control.
- Non-blocking and fault-tolerant: AWS failures never disrupt primary Supabase workflows.
- No public S3 ACLs; no credential exposure in logs or frontend.
"""

import os
import uuid
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# ── Feature Flags & Configuration ─────────────────────────────────────
def is_truthy(val: Optional[str]) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in ("true", "1", "yes", "on", "t")

AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
AWS_ENABLED = is_truthy(os.getenv("AWS_ENABLED", "true"))
AWS_S3_ENABLED = is_truthy(os.getenv("AWS_S3_ENABLED", "true")) and AWS_ENABLED
AWS_DYNAMODB_ENABLED = is_truthy(os.getenv("AWS_DYNAMODB_ENABLED", "true")) and AWS_ENABLED
AWS_SNS_ENABLED = is_truthy(os.getenv("AWS_SNS_ENABLED", "true")) and AWS_ENABLED
AWS_CLOUDWATCH_ENABLED = is_truthy(os.getenv("AWS_CLOUDWATCH_ENABLED", "true")) and AWS_ENABLED

# ── Resource Names ────────────────────────────────────────────────────
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "cspm-dustbin-images-koushik-2026")
AWS_DYNAMODB_TABLE = os.getenv("AWS_DYNAMODB_TABLE", "CSPM-Dustbin-Detections")
AWS_SNS_TOPIC_NAME = os.getenv("AWS_SNS_TOPIC_NAME", "CSPM-Dustbin-Alerts")
AWS_SNS_TOPIC_ARN = os.getenv("AWS_SNS_TOPIC_ARN", "")
AWS_CLOUDWATCH_LOG_GROUP = os.getenv("AWS_CLOUDWATCH_LOG_GROUP", "CSPM-Dustbin-Application-Logs")
AWS_CLOUDWATCH_LOG_STREAM = os.getenv("AWS_CLOUDWATCH_LOG_STREAM", "app-events")

# In-memory tracking of alert states to avoid repetitive notifications for unchanged critical state
# Format: {bin_id: {"last_status": "CRITICAL", "last_alert_time": timestamp, "message_id": id}}
_ALERT_STATE_CACHE: Dict[str, Dict[str, Any]] = {}

# Deduplication cooldown window (seconds) - default 1 hour
CRITICAL_ALERT_COOLDOWN_SECONDS = int(os.getenv("AWS_SNS_ALERT_COOLDOWN_SECONDS", "3600"))


class AWSServiceManager:
    """Manages AWS client lifecycles and operations."""

    def __init__(self):
        self._session: Optional[boto3.Session] = None
        self._s3_client = None
        self._dynamodb_resource = None
        self._sns_client = None
        self._logs_client = None
        arn_env = os.getenv("AWS_SNS_TOPIC_ARN", "").strip()
        self._cached_topic_arn: Optional[str] = arn_env or None
        self._stream_initialized: bool = False

    def get_session(self) -> boto3.Session:
        """Create or return existing boto3 Session with credential support."""
        if self._session is None:
            access_key = os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            session_token = os.getenv("AWS_SESSION_TOKEN")
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or AWS_REGION

            if access_key and secret_key:
                self._session = boto3.Session(
                    aws_access_key_id=access_key.strip(),
                    aws_secret_access_key=secret_key.strip(),
                    aws_session_token=session_token.strip() if session_token else None,
                    region_name=region
                )
            else:
                self._session = boto3.Session(region_name=region)
        return self._session

    def get_s3_client(self):
        if not AWS_S3_ENABLED:
            return None
        if self._s3_client is None:
            self._s3_client = self.get_session().client("s3")
        return self._s3_client

    def get_dynamodb_resource(self):
        if not AWS_DYNAMODB_ENABLED:
            return None
        if self._dynamodb_resource is None:
            self._dynamodb_resource = self.get_session().resource("dynamodb")
        return self._dynamodb_resource

    def get_sns_client(self):
        if not AWS_SNS_ENABLED:
            return None
        if self._sns_client is None:
            self._sns_client = self.get_session().client("sns")
        return self._sns_client

    def get_logs_client(self):
        if not AWS_CLOUDWATCH_ENABLED:
            return None
        if self._logs_client is None:
            self._logs_client = self.get_session().client("logs")
        return self._logs_client

    # ── CloudWatch Logging ────────────────────────────────────────────
    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        Record important events to CloudWatch and local logger.
        Sanitizes input to ensure no credentials or sensitive tokens are logged.
        """
        # Always log locally first
        sanitized_details = self._sanitize_details(details)
        log_msg = f"[AWS Event: {event_type}] {sanitized_details}"
        logger.info(log_msg)

        if not AWS_CLOUDWATCH_ENABLED:
            return

        try:
            client = self.get_logs_client()
            if not client:
                return

            self._ensure_log_stream(client)

            timestamp_ms = int(time.time() * 1000)
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "details": sanitized_details
            }

            import json
            client.put_log_events(
                logGroupName=AWS_CLOUDWATCH_LOG_GROUP,
                logStreamName=AWS_CLOUDWATCH_LOG_STREAM,
                logEvents=[
                    {
                        "timestamp": timestamp_ms,
                        "message": json.dumps(payload, default=str)
                    }
                ]
            )
        except Exception as e:
            # Gracefully log warning locally without interrupting application flow
            logger.warning(f"Failed to publish event to CloudWatch: {e}")

    def _ensure_log_stream(self, client) -> None:
        if self._stream_initialized:
            return
        try:
            client.create_log_stream(
                logGroupName=AWS_CLOUDWATCH_LOG_GROUP,
                logStreamName=AWS_CLOUDWATCH_LOG_STREAM
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
                logger.warning(f"CloudWatch stream creation note: {e}")
        except Exception as e:
            logger.warning(f"CloudWatch stream initialization note: {e}")
        self._stream_initialized = True

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Strip sensitive fields before logging."""
        sanitized = {}
        sensitive_keywords = {"token", "key", "secret", "password", "auth", "credential", "image_bytes", "base64"}
        for k, v in details.items():
            if any(sk in k.lower() for sk in sensitive_keywords):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    # ── Amazon S3 Archival Upload ─────────────────────────────────────
    def archive_image_to_s3(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "image/jpeg",
        bin_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Uploads an archival copy of the image to the existing S3 bucket.
        Preserves bucket privacy (no public ACLs).
        Returns the S3 object key or None on failure.
        """
        if not AWS_S3_ENABLED:
            return None

        try:
            s3 = self.get_s3_client()
            if not s3:
                return None

            now = datetime.now(timezone.utc)
            date_prefix = now.strftime("%Y/%m/%d")
            unique_token = uuid.uuid4().hex[:8]
            clean_filename = os.path.basename(filename).replace(" ", "_")
            
            bin_prefix = f"bins/bin-{bin_id}" if bin_id else "dustbin-images"
            object_key = f"{bin_prefix}/{date_prefix}/{unique_token}_{clean_filename}"

            # Put object with private access (no public ACL)
            s3.put_object(
                Bucket=AWS_S3_BUCKET,
                Key=object_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    "archived_at": now.isoformat(),
                    "bin_id": str(bin_id) if bin_id else "unassigned"
                }
            )

            self.log_event("S3_IMAGE_UPLOADED", {
                "bucket": AWS_S3_BUCKET,
                "object_key": object_key,
                "size_bytes": len(file_content),
                "bin_id": str(bin_id) if bin_id else None
            })
            return object_key

        except Exception as e:
            logger.warning(f"AWS S3 archive copy skipped or failed: {e}")
            self.log_event("AWS_INTEGRATION_ERROR", {
                "service": "S3",
                "operation": "archive_image_to_s3",
                "error": str(e)
            })
            return None

    # ── Amazon DynamoDB Synchronization ───────────────────────────────
    def sync_detection_to_dynamodb(
        self,
        bin_id: str,
        fill_level: float,
        waste_status: str,
        latitude: float,
        longitude: float,
        s3_object_key: Optional[str] = None,
        confidence: Optional[float] = None,
        report_id: Optional[int] = None,
        reason: Optional[str] = None,
        detection_timestamp: Optional[str] = None
    ) -> bool:
        """
        Synchronizes the latest detection result to DynamoDB table CSPM-Dustbin-Detections.
        Since partition key is bin_id, put_item maintains the latest state for that bin.
        Returns True on success, False on failure.
        """
        if not AWS_DYNAMODB_ENABLED:
            return False

        try:
            dynamodb = self.get_dynamodb_resource()
            if not dynamodb:
                return False

            table = dynamodb.Table(AWS_DYNAMODB_TABLE)
            iso_timestamp = detection_timestamp or datetime.now(timezone.utc).isoformat()

            # DynamoDB requires Decimal types for numeric floats
            item: Dict[str, Any] = {
                "bin_id": str(bin_id),
                "fill_level": Decimal(str(round(float(fill_level), 2))),
                "waste_status": str(waste_status).upper(),
                "latitude": Decimal(str(round(float(latitude), 7))),
                "longitude": Decimal(str(round(float(longitude), 7))),
                "detection_timestamp": iso_timestamp,
                "detection timestamp": iso_timestamp,  # exact phrasing support
                "last_updated": iso_timestamp
            }

            if s3_object_key:
                item["s3_object_key"] = str(s3_object_key)
            if confidence is not None:
                item["confidence"] = Decimal(str(round(float(confidence), 4)))
            if report_id is not None:
                item["report_id"] = int(report_id)
            if reason:
                item["analysis_reason"] = str(reason)[:500]

            table.put_item(Item=item)

            self.log_event("DYNAMODB_SYNC_SUCCESS", {
                "table": AWS_DYNAMODB_TABLE,
                "bin_id": str(bin_id),
                "waste_status": str(waste_status).upper(),
                "fill_level": round(float(fill_level), 2)
            })
            return True

        except Exception as e:
            logger.warning(f"DynamoDB sync failed for bin {bin_id}: {e}")
            self.log_event("DYNAMODB_SYNC_FAILED", {
                "table": AWS_DYNAMODB_TABLE,
                "bin_id": str(bin_id),
                "error": str(e)
            })
            self.log_event("AWS_INTEGRATION_ERROR", {
                "service": "DynamoDB",
                "operation": "sync_detection_to_dynamodb",
                "bin_id": str(bin_id),
                "error": str(e)
            })
            return False

    # ── Amazon SNS Critical Alerts ────────────────────────────────────
    def _resolve_topic_arn(self, sns_client) -> Optional[str]:
        """Resolves the ARN for the configured SNS topic."""
        if self._cached_topic_arn:
            return self._cached_topic_arn

        arn_env = os.getenv("AWS_SNS_TOPIC_ARN", "").strip()
        if arn_env:
            self._cached_topic_arn = arn_env
            return self._cached_topic_arn

        try:
            # Query SNS for the topic by name
            paginator = sns_client.get_paginator("list_topics")
            for page in paginator.paginate():
                for topic in page.get("Topics", []):
                    arn = topic.get("TopicArn", "")
                    if arn.endswith(f":{AWS_SNS_TOPIC_NAME}") or AWS_SNS_TOPIC_NAME in arn:
                        self._cached_topic_arn = arn
                        return arn
        except Exception as e:
            logger.warning(f"Could not list SNS topics dynamically: {e}")

        # Fallback to constructing canonical ARN if account ID is discoverable or default
        return None

    def publish_critical_alert(
        self,
        bin_id: str,
        waste_status: str,
        fill_level: float,
        latitude: float,
        longitude: float,
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
        report_id: Optional[int] = None,
        previous_status: Optional[str] = None
    ) -> Optional[str]:
        """
        Publishes an email notification to CSPM-Dustbin-Alerts only when status is CRITICAL.
        Implements state deduplication so alerts are not repeatedly triggered for unchanged critical states.
        Never alerts on normal/low/medium detections.
        Returns message_id on success or None.
        """
        if not AWS_SNS_ENABLED:
            return None

        # Only alert on CRITICAL
        if str(waste_status).upper() != "CRITICAL":
            return None

        # Deduplication check: Avoid repeatedly alerting for unchanged critical states
        now_ts = time.time()
        bin_key = str(bin_id)
        cached = _ALERT_STATE_CACHE.get(bin_key)

        # If previously critical and within cooldown, suppress duplicate alert
        if previous_status and str(previous_status).upper() == "CRITICAL":
            if cached and (now_ts - cached.get("last_alert_time", 0)) < CRITICAL_ALERT_COOLDOWN_SECONDS:
                logger.info(f"Skipping duplicate SNS alert for bin {bin_id}: already in CRITICAL state.")
                return None

        if cached and cached.get("last_status") == "CRITICAL":
            time_since_last = now_ts - cached.get("last_alert_time", 0)
            if time_since_last < CRITICAL_ALERT_COOLDOWN_SECONDS:
                logger.info(f"Skipping repeated SNS alert for bin {bin_id}: alerted {int(time_since_last)}s ago.")
                return None

        try:
            sns = self.get_sns_client()
            if not sns:
                return None

            topic_arn = self._resolve_topic_arn(sns)
            if not topic_arn:
                logger.warning(f"SNS Topic ARN for {AWS_SNS_TOPIC_NAME} could not be resolved.")
                return None

            subject = f"[URGENT] CSPM Dustbin Critical Alert - Bin {bin_id}"
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            body_lines = [
                "==================================================",
                "CSPM DUSTBIN LEVEL DETECTION — CRITICAL ALERT",
                "==================================================",
                "",
                f"Dustbin ID:       {bin_id}",
                f"Waste Status:     CRITICAL (Overflow Hazard)",
                f"Current Level:    {round(float(fill_level), 1)}%",
                f"Coordinates:      Latitude {latitude:.6f}, Longitude {longitude:.6f}",
                f"Detection Time:   {now_iso}",
            ]
            if confidence is not None:
                body_lines.append(f"AI Confidence:    {float(confidence):.2%}")
            if report_id:
                body_lines.append(f"Report Reference: #{report_id}")
            if reason:
                body_lines.append(f"Observation:      {reason}")

            body_lines.extend([
                "",
                "ACTION REQUIRED:",
                "This dustbin has exceeded critical capacity thresholds.",
                "Please dispatch municipal collection trucks immediately to prevent street spillover.",
                "",
                "Automated notification sent by CSPM Smart Waste Management System.",
                "=================================================="
            ])

            message_body = "\n".join(body_lines)

            response = sns.publish(
                TopicArn=topic_arn,
                Subject=subject[:100],  # SNS subject max 100 characters
                Message=message_body
            )

            message_id = response.get("MessageId")

            # Update cache to suppress repeated notifications for this critical cycle
            _ALERT_STATE_CACHE[bin_key] = {
                "last_status": "CRITICAL",
                "last_alert_time": now_ts,
                "message_id": message_id
            }

            self.log_event("SNS_CRITICAL_ALERT_PUBLISHED", {
                "topic": AWS_SNS_TOPIC_NAME,
                "topic_arn": topic_arn,
                "bin_id": bin_key,
                "message_id": message_id,
                "fill_level": round(float(fill_level), 1)
            })

            return message_id

        except Exception as e:
            logger.warning(f"SNS critical alert publication failed: {e}")
            self.log_event("AWS_INTEGRATION_ERROR", {
                "service": "SNS",
                "operation": "publish_critical_alert",
                "bin_id": bin_key,
                "error": str(e)
            })
            return None

    # ── Combined Post-Detection Pipeline Helper ────────────────────────
    def process_detection_aws_integrations(
        self,
        bin_id: str,
        fill_level: float,
        waste_status: str,
        latitude: float,
        longitude: float,
        s3_object_key: Optional[str] = None,
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
        report_id: Optional[int] = None,
        previous_status: Optional[str] = None,
        ai_provider: Optional[str] = "NVIDIA NIM",
        ai_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates all post-AI detection AWS integrations:
        1. CloudWatch event: AI detection completed.
        2. DynamoDB: Put latest detection record.
        3. SNS: Publish critical alert if status is CRITICAL and state changed.
        Never throws exceptions; returns status summary.
        """
        results: Dict[str, Any] = {
            "cloudwatch_logged": False,
            "dynamodb_synced": False,
            "sns_alert_sent": False,
            "sns_message_id": None
        }

        # 1. Log AI Detection Completion
        try:
            self.log_event("AI_DETECTION_COMPLETED", {
                "bin_id": str(bin_id),
                "report_id": report_id,
                "waste_status": str(waste_status).upper(),
                "confidence": float(confidence) if confidence is not None else None,
                "fill_level": round(float(fill_level), 2),
                "provider": ai_provider,
                "model": ai_model
            })
            if AWS_CLOUDWATCH_ENABLED:
                results["cloudwatch_logged"] = True
        except Exception as e:
            logger.warning(f"CloudWatch log step failed: {e}")

        # 2. Synchronize to DynamoDB
        try:
            results["dynamodb_synced"] = self.sync_detection_to_dynamodb(
                bin_id=str(bin_id),
                fill_level=fill_level,
                waste_status=waste_status,
                latitude=latitude,
                longitude=longitude,
                s3_object_key=s3_object_key,
                confidence=confidence,
                report_id=report_id,
                reason=reason
            )
        except Exception as e:
            logger.warning(f"DynamoDB step failed: {e}")

        # 3. Publish SNS Alert (if Critical)
        try:
            msg_id = self.publish_critical_alert(
                bin_id=str(bin_id),
                waste_status=waste_status,
                fill_level=fill_level,
                latitude=latitude,
                longitude=longitude,
                confidence=confidence,
                reason=reason,
                report_id=report_id,
                previous_status=previous_status
            )
            if msg_id:
                results["sns_alert_sent"] = True
                results["sns_message_id"] = msg_id
        except Exception as e:
            logger.warning(f"SNS alert step failed: {e}")

        return results


# Global singleton instance
aws_service = AWSServiceManager()

