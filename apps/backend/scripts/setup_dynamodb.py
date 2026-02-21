"""
Idempotent DynamoDB table setup.

Creates the 4 AutoEval-Sum tables if they do not already exist.
Safe to run repeatedly — existing tables are left untouched.

Usage:
    uv run python scripts/setup_dynamodb.py
    # or inside compose via setup-dynamo service
"""

import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")
REGION = os.getenv("AWS_REGION", "us-east-1")

# ---------------------------------------------------------------------------
# Table definitions
# Each entry: (table_name, key_schema, attribute_definitions, billing_mode)
# ---------------------------------------------------------------------------
TABLES = [
    {
        "TableName": "AutoEvalRuns",
        "KeySchema": [
            {"AttributeName": "run_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "run_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "Documents",
        "KeySchema": [
            {"AttributeName": "doc_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "doc_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "EvalSuites",
        # pk=run_id  sk=suite_version ("v1" | "v2")
        # Allows: query all suites for a given run
        "KeySchema": [
            {"AttributeName": "run_id", "KeyType": "HASH"},
            {"AttributeName": "suite_version", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "run_id", "AttributeType": "S"},
            {"AttributeName": "suite_version", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "EvalResults",
        # pk=suite_id ("{run_id}#v{n}")  sk=eval_id ("v{n}-case-{0001}")
        # Allows: query all results for a given suite
        "KeySchema": [
            {"AttributeName": "suite_id", "KeyType": "HASH"},
            {"AttributeName": "eval_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "suite_id", "AttributeType": "S"},
            {"AttributeName": "eval_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
]


def _table_exists(client: boto3.client, table_name: str) -> bool:
    try:
        client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def _wait_for_active(client: boto3.client, table_name: str) -> None:
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name, WaiterConfig={"Delay": 2, "MaxAttempts": 15})


def setup_tables() -> None:
    client = boto3.client(
        "dynamodb",
        region_name=REGION,
        endpoint_url=ENDPOINT_URL,
        # Local DynamoDB accepts any credentials
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    log.info("Connecting to DynamoDB at %s", ENDPOINT_URL)

    created = 0
    skipped = 0

    for table_def in TABLES:
        name = table_def["TableName"]
        if _table_exists(client, name):
            log.info("  ✓ %s already exists — skipping", name)
            skipped += 1
            continue

        log.info("  + Creating %s …", name)
        client.create_table(**table_def)
        _wait_for_active(client, name)
        log.info("  ✓ %s created", name)
        created += 1

    log.info("Done — %d created, %d already existed.", created, skipped)


if __name__ == "__main__":
    try:
        setup_tables()
    except Exception as exc:
        log.error("DynamoDB setup failed: %s", exc)
        sys.exit(1)
