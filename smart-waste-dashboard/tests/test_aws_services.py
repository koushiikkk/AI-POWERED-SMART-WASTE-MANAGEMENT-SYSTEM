"""
Unit and Integration Tests for AWS Cloud Services in CSPM Dustbin Level Detection.

Uses moto to mock:
- Amazon S3 (cspm-dustbin-images-koushik-2026)
- Amazon DynamoDB (CSPM-Dustbin-Detections)
- Amazon SNS (CSPM-Dustbin-Alerts)
- Amazon CloudWatch (CSPM-Dustbin-Application-Logs)

Verifies:
1. S3 archival copy upload, key structure, and privacy.
2. DynamoDB sync with partition key 'bin_id' ensuring latest record state.
3. SNS critical-only alerting with deduplication for unchanged critical states.
4. CloudWatch event logging with credential sanitization.
5. Graceful fault tolerance when AWS services fail.
6. Feature flags for independent enablement/disablement.
"""

import os
import sys
import time
from decimal import Decimal
import pytest
import boto3
from moto import mock_aws

# Ensure backend directory is in python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.aws_service import (
    aws_service,
    AWSServiceManager,
    _ALERT_STATE_CACHE,
    AWS_S3_BUCKET,
    AWS_DYNAMODB_TABLE,
    AWS_SNS_TOPIC_NAME,
    AWS_CLOUDWATCH_LOG_GROUP,
    AWS_CLOUDWATCH_LOG_STREAM,
)

REGION = "us-east-1"


@pytest.fixture(autouse=True)
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing-access-key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing-secret-key"
    os.environ["AWS_SESSION_TOKEN"] = "testing-session-token"
    os.environ["AWS_DEFAULT_REGION"] = REGION
    os.environ["AWS_REGION"] = REGION
    os.environ["AWS_ENABLED"] = "true"
    os.environ["AWS_S3_ENABLED"] = "true"
    os.environ["AWS_DYNAMODB_ENABLED"] = "true"
    os.environ["AWS_SNS_ENABLED"] = "true"
    os.environ["AWS_SNS_TOPIC_ARN"] = ""
    os.environ["AWS_CLOUDWATCH_ENABLED"] = "true"
    import app.services.aws_service as aws_mod
    aws_mod.AWS_ENABLED = True
    aws_mod.AWS_S3_ENABLED = True
    aws_mod.AWS_DYNAMODB_ENABLED = True
    aws_mod.AWS_SNS_ENABLED = True
    aws_mod.AWS_CLOUDWATCH_ENABLED = True
    _ALERT_STATE_CACHE.clear()


@pytest.fixture
def fresh_aws_manager():
    """Returns a fresh AWSServiceManager instance for clean client states."""
    manager = AWSServiceManager()
    return manager


# ══════════════════════════════════════════════════════════════════════════════
# A. Amazon S3 Tests
# ══════════════════════════════════════════════════════════════════════════════

@mock_aws
def test_s3_archive_upload_success(fresh_aws_manager):
    """Verify image is uploaded to the correct bucket with an organized key."""
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket=AWS_S3_BUCKET)

    sample_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01"
    filename = "bin_camera_capture.jpg"
    bin_id = "BIN-42"

    object_key = fresh_aws_manager.archive_image_to_s3(
        file_content=sample_bytes,
        filename=filename,
        content_type="image/jpeg",
        bin_id=bin_id
    )

    assert object_key is not None
    assert f"bins/bin-{bin_id}/" in object_key
    assert object_key.endswith(".jpg")

    # Verify object in S3
    head = s3.head_object(Bucket=AWS_S3_BUCKET, Key=object_key)
    assert head["ContentLength"] == len(sample_bytes)
    assert head["ContentType"] == "image/jpeg"
    assert head["Metadata"]["bin_id"] == bin_id


@mock_aws
def test_s3_upload_preserves_privacy_no_public_access(fresh_aws_manager):
    """Verify uploaded S3 object does NOT have public-read grant."""
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket=AWS_S3_BUCKET)

    object_key = fresh_aws_manager.archive_image_to_s3(
        file_content=b"test-bytes",
        filename="test.png",
        content_type="image/png"
    )
    assert object_key is not None

    acl = s3.get_object_acl(Bucket=AWS_S3_BUCKET, Key=object_key)
    # Check that no grantee is AllUsers
    grantees = [g.get("Grantee", {}).get("URI", "") for g in acl.get("Grants", [])]
    assert not any("AllUsers" in uri for uri in grantees)


@mock_aws
def test_s3_failure_is_fault_tolerant(fresh_aws_manager):
    """Verify that if S3 bucket does not exist, upload fails gracefully returning None."""
    # Bucket is NOT created in moto
    object_key = fresh_aws_manager.archive_image_to_s3(
        file_content=b"test-bytes",
        filename="broken.jpg"
    )
    # Must NOT raise exception; returns None
    assert object_key is None


# ══════════════════════════════════════════════════════════════════════════════
# B. Amazon DynamoDB Tests
# ══════════════════════════════════════════════════════════════════════════════

def _create_dynamodb_table():
    client = boto3.client("dynamodb", region_name=REGION)
    client.create_table(
        TableName=AWS_DYNAMODB_TABLE,
        KeySchema=[{"AttributeName": "bin_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "bin_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST"
    )


@mock_aws
def test_dynamodb_sync_success(fresh_aws_manager):
    """Verify detection data is saved with correct attributes and types."""
    _create_dynamodb_table()

    success = fresh_aws_manager.sync_detection_to_dynamodb(
        bin_id="BIN-101",
        fill_level=87.5,
        waste_status="HIGH",
        latitude=13.0827,
        longitude=80.2707,
        s3_object_key="bins/bin-101/2026/11/img.jpg",
        confidence=0.92,
        report_id=7,
        reason="Noticeable overflow around rim"
    )

    assert success is True

    # Read back from DynamoDB
    table = boto3.resource("dynamodb", region_name=REGION).Table(AWS_DYNAMODB_TABLE)
    item = table.get_item(Key={"bin_id": "BIN-101"}).get("Item")

    assert item is not None
    assert item["bin_id"] == "BIN-101"
    assert item["waste_status"] == "HIGH"
    assert item["fill_level"] == Decimal("87.5")
    assert item["latitude"] == Decimal("13.0827")
    assert item["longitude"] == Decimal("80.2707")
    assert item["s3_object_key"] == "bins/bin-101/2026/11/img.jpg"
    assert item["confidence"] == Decimal("0.92")
    assert item["report_id"] == 7
    assert "detection_timestamp" in item
    assert "detection timestamp" in item


@mock_aws
def test_dynamodb_maintains_latest_record_per_bin(fresh_aws_manager):
    """Verify that multiple syncs for the same bin_id overwrite to maintain the latest status."""
    _create_dynamodb_table()
    table = boto3.resource("dynamodb", region_name=REGION).Table(AWS_DYNAMODB_TABLE)

    # Initial detection: MEDIUM
    fresh_aws_manager.sync_detection_to_dynamodb(
        bin_id="BIN-202",
        fill_level=55.0,
        waste_status="MEDIUM",
        latitude=12.9716,
        longitude=77.5946
    )

    item1 = table.get_item(Key={"bin_id": "BIN-202"}).get("Item")
    assert item1["waste_status"] == "MEDIUM"
    assert item1["fill_level"] == Decimal("55.0")

    # Later detection: CRITICAL
    fresh_aws_manager.sync_detection_to_dynamodb(
        bin_id="BIN-202",
        fill_level=96.0,
        waste_status="CRITICAL",
        latitude=12.9716,
        longitude=77.5946
    )

    item2 = table.get_item(Key={"bin_id": "BIN-202"}).get("Item")
    assert item2["waste_status"] == "CRITICAL"
    assert item2["fill_level"] == Decimal("96.0")

    # Table item count should still be 1 (partition key maintains latest state)
    scan_res = table.scan()
    assert scan_res["Count"] == 1


@mock_aws
def test_dynamodb_failure_is_fault_tolerant(fresh_aws_manager):
    """Verify missing table does not crash the system."""
    # Table NOT created
    success = fresh_aws_manager.sync_detection_to_dynamodb(
        bin_id="BIN-999",
        fill_level=50.0,
        waste_status="LOW",
        latitude=0.0,
        longitude=0.0
    )
    assert success is False


# ══════════════════════════════════════════════════════════════════════════════
# C. Amazon SNS Alert Tests
# ══════════════════════════════════════════════════════════════════════════════

def _create_sns_topic():
    sns = boto3.client("sns", region_name=REGION)
    res = sns.create_topic(Name=AWS_SNS_TOPIC_NAME)
    return res["TopicArn"]


@mock_aws
def test_sns_critical_alert_published(fresh_aws_manager):
    """Verify alert is published when status is CRITICAL."""
    topic_arn = _create_sns_topic()

    msg_id = fresh_aws_manager.publish_critical_alert(
        bin_id="BIN-303",
        waste_status="CRITICAL",
        fill_level=98.0,
        latitude=13.0827,
        longitude=80.2707,
        confidence=0.95,
        reason="Severe garbage spill onto street sidewalk",
        report_id=12,
        previous_status="MEDIUM"
    )

    assert msg_id is not None
    assert len(msg_id) > 0


@mock_aws
def test_sns_ignores_normal_and_high_detections(fresh_aws_manager):
    """Verify notifications are NEVER sent for normal, LOW, MEDIUM, or HIGH detections."""
    _create_sns_topic()

    for non_critical in ["LOW", "MEDIUM", "HIGH", "NORMAL", "UNKNOWN"]:
        msg_id = fresh_aws_manager.publish_critical_alert(
            bin_id="BIN-NON-CRITICAL",
            waste_status=non_critical,
            fill_level=40.0,
            latitude=13.0,
            longitude=80.0
        )
        assert msg_id is None, f"Expected no alert for {non_critical}, but got msg_id {msg_id}"


@mock_aws
def test_sns_deduplication_for_unchanged_critical_state(fresh_aws_manager):
    """Verify alerts are NOT repeatedly sent when a bin remains in unchanged critical state."""
    _create_sns_topic()

    # 1. First time critical -> Alert should be sent
    first_msg = fresh_aws_manager.publish_critical_alert(
        bin_id="BIN-DUP-TEST",
        waste_status="CRITICAL",
        fill_level=94.0,
        latitude=13.0,
        longitude=80.0,
        previous_status="HIGH"
    )
    assert first_msg is not None

    # 2. Second detection with unchanged CRITICAL state within cooldown -> Alert must be suppressed
    second_msg = fresh_aws_manager.publish_critical_alert(
        bin_id="BIN-DUP-TEST",
        waste_status="CRITICAL",
        fill_level=95.0,
        latitude=13.0,
        longitude=80.0,
        previous_status="CRITICAL"
    )
    assert second_msg is None, "Repeated critical alert was not suppressed!"


# ══════════════════════════════════════════════════════════════════════════════
# D. Amazon CloudWatch Logging Tests
# ══════════════════════════════════════════════════════════════════════════════

def _create_cloudwatch_log_group():
    logs = boto3.client("logs", region_name=REGION)
    try:
        logs.create_log_group(logGroupName=AWS_CLOUDWATCH_LOG_GROUP)
    except Exception:
        pass


@mock_aws
def test_cloudwatch_logging_and_sanitization(fresh_aws_manager):
    """Verify log events are recorded and credentials are redacted."""
    _create_cloudwatch_log_group()

    # Log an event containing potentially sensitive keys
    fresh_aws_manager.log_event("AI_DETECTION_COMPLETED", {
        "bin_id": "BIN-CW-1",
        "fill_level": 92.0,
        "auth_token": "secret-bearer-token-12345",
        "api_key": "nvapi-secret-key-abcdef",
        "user_password": "super-secret-password"
    })

    logs = boto3.client("logs", region_name=REGION)
    events = logs.get_log_events(
        logGroupName=AWS_CLOUDWATCH_LOG_GROUP,
        logStreamName=AWS_CLOUDWATCH_LOG_STREAM
    ).get("events", [])

    assert len(events) >= 1
    msg_text = events[0]["message"]

    assert "BIN-CW-1" in msg_text
    assert "[REDACTED]" in msg_text
    assert "secret-bearer-token-12345" not in msg_text
    assert "nvapi-secret-key-abcdef" not in msg_text
    assert "super-secret-password" not in msg_text


# ══════════════════════════════════════════════════════════════════════════════
# E. End-to-End AWS Pipeline Orchestration
# ══════════════════════════════════════════════════════════════════════════════

@mock_aws
def test_process_detection_aws_integrations_pipeline(fresh_aws_manager):
    """Verify post-detection helper coordinates CloudWatch, DynamoDB, and SNS seamlessly."""
    _create_cloudwatch_log_group()
    _create_dynamodb_table()
    _create_sns_topic()

    summary = fresh_aws_manager.process_detection_aws_integrations(
        bin_id="BIN-PIPELINE-1",
        fill_level=97.0,
        waste_status="CRITICAL",
        latitude=13.0827,
        longitude=80.2707,
        confidence=0.91,
        reason="Container overflowing on sidewalk",
        report_id=99,
        previous_status="LOW"
    )

    assert summary["cloudwatch_logged"] is True
    assert summary["dynamodb_synced"] is True
    assert summary["sns_alert_sent"] is True
    assert summary["sns_message_id"] is not None


@mock_aws
def test_feature_flags_disable_aws_services(fresh_aws_manager):
    """Verify individual feature flags properly disable respective services without errors."""
    import app.services.aws_service as aws_mod
    original_flags = (
        aws_mod.AWS_S3_ENABLED,
        aws_mod.AWS_DYNAMODB_ENABLED,
        aws_mod.AWS_SNS_ENABLED,
        aws_mod.AWS_CLOUDWATCH_ENABLED
    )

    try:
        aws_mod.AWS_S3_ENABLED = False
        aws_mod.AWS_DYNAMODB_ENABLED = False
        aws_mod.AWS_SNS_ENABLED = False
        aws_mod.AWS_CLOUDWATCH_ENABLED = False

        # None of these should raise or attempt AWS operations
        assert fresh_aws_manager.archive_image_to_s3(b"bytes", "img.jpg") is None
        assert fresh_aws_manager.sync_detection_to_dynamodb("BIN-1", 50.0, "LOW", 0.0, 0.0) is False
        assert fresh_aws_manager.publish_critical_alert("BIN-1", "CRITICAL", 99.0, 0.0, 0.0) is None
        fresh_aws_manager.log_event("TEST_EVENT", {"test": True})  # silent pass

    finally:
        (
            aws_mod.AWS_S3_ENABLED,
            aws_mod.AWS_DYNAMODB_ENABLED,
            aws_mod.AWS_SNS_ENABLED,
            aws_mod.AWS_CLOUDWATCH_ENABLED
        ) = original_flags


@mock_aws
def test_all_aws_services_globally_disabled(fresh_aws_manager):
    """Verify that when AWS_ENABLED is False, the full detection pipeline gracefully skips everything."""
    import app.services.aws_service as aws_mod
    original_flags = (
        aws_mod.AWS_ENABLED,
        aws_mod.AWS_S3_ENABLED,
        aws_mod.AWS_DYNAMODB_ENABLED,
        aws_mod.AWS_SNS_ENABLED,
        aws_mod.AWS_CLOUDWATCH_ENABLED
    )

    try:
        aws_mod.AWS_ENABLED = False
        aws_mod.AWS_S3_ENABLED = False
        aws_mod.AWS_DYNAMODB_ENABLED = False
        aws_mod.AWS_SNS_ENABLED = False
        aws_mod.AWS_CLOUDWATCH_ENABLED = False

        res = fresh_aws_manager.process_detection_aws_integrations(
            bin_id="BIN-DISABLED-TEST",
            fill_level=95.0,
            waste_status="CRITICAL",
            latitude=13.0827,
            longitude=80.2707,
            confidence=0.99,
            reason="Overflow hazard"
        )

        assert res["cloudwatch_logged"] is False
        assert res["dynamodb_synced"] is False
        assert res["sns_alert_sent"] is False
        assert res["sns_message_id"] is None
        assert fresh_aws_manager.archive_image_to_s3(b"image", "img.jpg") is None

    finally:
        (
            aws_mod.AWS_ENABLED,
            aws_mod.AWS_S3_ENABLED,
            aws_mod.AWS_DYNAMODB_ENABLED,
            aws_mod.AWS_SNS_ENABLED,
            aws_mod.AWS_CLOUDWATCH_ENABLED
        ) = original_flags


if __name__ == "__main__":
    pytest.main(["-v", __file__])

