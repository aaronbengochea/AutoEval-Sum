"""
FastAPI dependency providers.

One generator per DynamoDB table following the deepthought pattern.
Import and use with FastAPI's Depends() in route functions.
"""

from collections.abc import Generator

from autoeval_sum.config.settings import get_settings
from autoeval_sum.db.client import DynamoDBClient


def get_documents_db() -> Generator[DynamoDBClient, None, None]:
    settings = get_settings()
    yield DynamoDBClient(
        table_name=settings.dynamodb_documents_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )


def get_runs_db() -> Generator[DynamoDBClient, None, None]:
    settings = get_settings()
    yield DynamoDBClient(
        table_name=settings.dynamodb_runs_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )


def get_suites_db() -> Generator[DynamoDBClient, None, None]:
    settings = get_settings()
    yield DynamoDBClient(
        table_name=settings.dynamodb_suites_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )


def get_results_db() -> Generator[DynamoDBClient, None, None]:
    settings = get_settings()
    yield DynamoDBClient(
        table_name=settings.dynamodb_results_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url,
    )
