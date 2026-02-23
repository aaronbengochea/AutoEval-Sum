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

ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL")
REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY")

# ---------------------------------------------------------------------------
# Table definitions
# Each entry: (table_name, key_schema, attribute_definitions, billing_mode)
# ---------------------------------------------------------------------------
# All tables use the generic "pk" (hash) and "sk" (range) attribute names,
# matching the DynamoDBClient which always builds Keys as {"pk": ..., "sk": ...}.
# Domain-specific IDs (run_id, doc_id, etc.) are stored as regular item attributes.
TABLES = [
    {
        "TableName": "AutoEvalRuns",
        # pk = run_id (UUIDv7)
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "Documents",
        # pk = doc_id (SHA-256 stable ID)
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "EvalSuites",
        # pk = run_id  sk = suite_version ("v1" | "v2")
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    {
        "TableName": "EvalResults",
        # pk = suite_id ("{run_id}#v{n}")  sk = eval_id ("v{n}-case-{0001}")
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
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
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
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
