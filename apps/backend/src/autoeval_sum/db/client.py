"""
Async DynamoDB client wrapper.

Thin async abstraction over aioboto3 following the deepthought pattern.
One client instance is created per table; dependency injection provides
the right instance to each route via FastAPI Depends.

Key conventions
---------------
- All items use string keys ``pk`` (partition) and optionally ``sk`` (sort).
- float values must be converted to Decimal before writes (DynamoDB limitation).
- Timestamps are stored as UTC ISO 8601 strings.
"""

import logging
from decimal import Decimal
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


# ── Type helpers ──────────────────────────────────────────────────────────────

def floats_to_decimals(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: floats_to_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [floats_to_decimals(v) for v in obj]
    return obj


def decimals_to_floats(obj: Any) -> Any:
    """Recursively convert Decimal values back to float after DynamoDB reads.

    boto3/aioboto3 returns all numeric attributes as Decimal.  Without this
    conversion Pydantic serialises Decimal as a string in dict[str, Any] fields,
    which breaks any frontend code that calls .toFixed() on the received value.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimals_to_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimals_to_floats(v) for v in obj]
    return obj


# ── Client ────────────────────────────────────────────────────────────────────

class DynamoDBClient:
    """Async DynamoDB table client."""

    def __init__(
        self,
        table_name: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ) -> None:
        self.table_name = table_name
        self.region = region
        self.endpoint_url = endpoint_url
        self._session = aioboto3.Session()

    def _resource_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "region_name": self.region,
            # Local DynamoDB accepts any credentials
            "aws_access_key_id": "local",
            "aws_secret_access_key": "local",
        }
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return kwargs

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_item(self, pk: str, sk: str | None = None) -> dict[str, Any] | None:
        """Fetch a single item by primary key.  Returns None if not found."""
        try:
            async with self._session.resource("dynamodb", **self._resource_kwargs()) as ddb:
                table = await ddb.Table(self.table_name)
                key: dict[str, str] = {"pk": pk}
                if sk is not None:
                    key["sk"] = sk
                response = await table.get_item(Key=key)
                item = response.get("Item")
                return decimals_to_floats(item) if item is not None else None
        except ClientError as exc:
            raise RuntimeError(
                f"DynamoDB get_item failed on {self.table_name}: {exc}"
            ) from exc

    async def query(
        self,
        pk: str,
        sk_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query all items for a partition key, optionally filtering by sk prefix."""
        try:
            async with self._session.resource("dynamodb", **self._resource_kwargs()) as ddb:
                table = await ddb.Table(self.table_name)

                key_condition = "pk = :pk"
                expr_values: dict[str, Any] = {":pk": pk}

                if sk_prefix:
                    key_condition += " AND begins_with(sk, :sk_prefix)"
                    expr_values[":sk_prefix"] = sk_prefix

                kwargs: dict[str, Any] = {
                    "KeyConditionExpression": key_condition,
                    "ExpressionAttributeValues": expr_values,
                }
                if limit is not None:
                    kwargs["Limit"] = limit

                response = await table.query(**kwargs)
                return [decimals_to_floats(i) for i in response.get("Items", [])]
        except ClientError as exc:
            raise RuntimeError(
                f"DynamoDB query failed on {self.table_name}: {exc}"
            ) from exc

    # ── Write ─────────────────────────────────────────────────────────────────

    async def put_item(self, item: dict[str, Any]) -> None:
        """Create or overwrite an item.  Floats are auto-converted to Decimal."""
        try:
            async with self._session.resource("dynamodb", **self._resource_kwargs()) as ddb:
                table = await ddb.Table(self.table_name)
                await table.put_item(Item=floats_to_decimals(item))
        except ClientError as exc:
            raise RuntimeError(
                f"DynamoDB put_item failed on {self.table_name}: {exc}"
            ) from exc

    async def update_item(
        self,
        pk: str,
        sk: str | None,
        updates: dict[str, Any],
    ) -> None:
        """Partial update using SET expressions."""
        try:
            async with self._session.resource("dynamodb", **self._resource_kwargs()) as ddb:
                table = await ddb.Table(self.table_name)

                set_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
                attr_names = {f"#{k}": k for k in updates}
                attr_values = {f":{k}": floats_to_decimals(v) for k, v in updates.items()}

                key: dict[str, str] = {"pk": pk}
                if sk is not None:
                    key["sk"] = sk

                await table.update_item(
                    Key=key,
                    UpdateExpression=set_expr,
                    ExpressionAttributeNames=attr_names,
                    ExpressionAttributeValues=attr_values,
                )
        except ClientError as exc:
            raise RuntimeError(
                f"DynamoDB update_item failed on {self.table_name}: {exc}"
            ) from exc

    async def delete_item(self, pk: str, sk: str | None = None) -> None:
        """Delete a single item by primary key."""
        try:
            async with self._session.resource("dynamodb", **self._resource_kwargs()) as ddb:
                table = await ddb.Table(self.table_name)
                key: dict[str, str] = {"pk": pk}
                if sk is not None:
                    key["sk"] = sk
                await table.delete_item(Key=key)
        except ClientError as exc:
            raise RuntimeError(
                f"DynamoDB delete_item failed on {self.table_name}: {exc}"
            ) from exc

    async def scan_all(self) -> list[dict[str, Any]]:
        """Full table scan — use only for small tables or admin tooling."""
        try:
            async with self._session.resource("dynamodb", **self._resource_kwargs()) as ddb:
                table = await ddb.Table(self.table_name)
                items: list[dict[str, Any]] = []
                response = await table.scan()
                items.extend(response.get("Items", []))

                while "LastEvaluatedKey" in response:
                    response = await table.scan(
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                    items.extend(response.get("Items", []))

                return [decimals_to_floats(i) for i in items]
        except ClientError as exc:
            raise RuntimeError(
                f"DynamoDB scan failed on {self.table_name}: {exc}"
            ) from exc
