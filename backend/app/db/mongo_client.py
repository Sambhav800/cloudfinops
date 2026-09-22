"""
MongoDB-backed database client.

This provides the core database interface for the backend, using MongoDB
collections for persistence.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import ASCENDING, DESCENDING, UpdateOne

from ..config import get_settings
from ..core.finance import aggregate_daily_spend_rows
from .resource_contract import normalize_resource_row, normalize_resource_batch

logger = logging.getLogger(__name__)

ALLOWED_PROVIDERS = {"aws", "azure", "gcp"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {key: _deep_serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_serialize(item) for item in value]
    return value


def _strip_mongo_id(document: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(document)
    mongo_id = doc.pop("_id", None)
    if not doc.get("id") and mongo_id is not None:
        doc["id"] = str(mongo_id)
    return _deep_serialize(doc)


def _projection_from_columns(columns: str) -> Optional[Dict[str, int]]:
    if columns.strip() == "*":
        return None

    projection: Dict[str, int] = {"_id": 0}
    for raw_column in columns.split(","):
        column = raw_column.strip()
        if column:
            projection[column] = 1
    return projection


def _normalize_provider(value: Any) -> str:
    provider = str(value or "").strip().lower()
    if provider in ALLOWED_PROVIDERS:
        return provider
    raise ValueError("provider must be explicitly set to one of: aws, azure, gcp")


def _to_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if parsed != parsed else parsed


class MongoDBClient:
    """MongoDB client providing the core database interface."""

    def __init__(self, mongodb_uri: str, database_name: str):
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._indexes_ready = False
        # Kept for backwards compatibility with debugging scripts.
        self.headers: Dict[str, str] = {}

    async def _get_client(self) -> AsyncIOMotorClient:
        if self._client is None:
            self._client = AsyncIOMotorClient(
                self.mongodb_uri,
                maxPoolSize=20,
                minPoolSize=2,
                maxIdleTimeMS=30_000,
                serverSelectionTimeoutMS=5_000,
                connectTimeoutMS=5_000,
                socketTimeoutMS=30_000,
            )
        return self._client

    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            client = await self._get_client()
            self._db = client[self.database_name]

        if not self._indexes_ready:
            await self._ensure_indexes()
            self._indexes_ready = True

        return self._db

    async def _collection(self, table: str) -> AsyncIOMotorCollection:
        db = await self._get_db()
        return db[table]

    async def _ensure_indexes(self) -> None:
        """
        Create critical indexes once per process.
        """
        try:
            db = self._db
            if db is None:
                return

            async def ensure_index(
                collection_name: str,
                keys: list[tuple[str, int]],
                **options: Any,
            ) -> None:
                collection = db[collection_name]
                index_name = options.get("name")
                if not index_name:
                    index_name = "_".join(f"{field}_{direction}" for field, direction in keys)
                    options["name"] = index_name

                try:
                    existing_indexes = await collection.index_information()
                except Exception:
                    existing_indexes = {}

                existing = existing_indexes.get(index_name)
                desired_partial = options.get("partialFilterExpression")
                if existing:
                    existing_partial = existing.get("partialFilterExpression")
                    existing_sparse = existing.get("sparse")
                    if existing_sparse or existing_partial != desired_partial:
                        await collection.drop_index(index_name)

                await collection.create_index(keys, **options)

            await ensure_index("cloud_integrations", [("id", ASCENDING)], unique=True)
            await ensure_index("cloud_integrations", [("user_id", ASCENDING), ("status", ASCENDING)])
            await ensure_index("cloud_integrations", [("provider", ASCENDING)])
            await ensure_index("users", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "users",
                [("email_lower", ASCENDING)],
                unique=True,
                partialFilterExpression={"email_lower": {"$type": "string"}},
            )

            await ensure_index("resources", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "resources",
                [("integration_id", ASCENDING), ("cloud_resource_id", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "integration_id": {"$type": "string"},
                    "cloud_resource_id": {"$type": "string"},
                },
            )
            await ensure_index("resources", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("resources", [("provider", ASCENDING)])
            await ensure_index(
                "cloud_price_catalog",
                [("provider", ASCENDING), ("catalog_key", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "provider": {"$type": "string"},
                    "catalog_key": {"$type": "string"},
                },
            )
            await ensure_index(
                "cloud_price_catalog",
                [("provider", ASCENDING), ("service_code", ASCENDING), ("region", ASCENDING)],
            )
            await ensure_index(
                "cloud_price_catalog_syncs",
                [("provider", ASCENDING), ("source", ASCENDING), ("service_code", ASCENDING), ("region", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "provider": {"$type": "string"},
                    "source": {"$type": "string"},
                },
            )

            await ensure_index("scan_history", [("id", ASCENDING)], unique=True)
            await ensure_index("scan_history", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("scan_history", [("user_id", ASCENDING), ("integration_id", ASCENDING), ("started_at", DESCENDING)])

            await ensure_index(
                "dashboard_stats",
                [("integration_id", ASCENDING)],
                unique=True,
                partialFilterExpression={"integration_id": {"$type": "string"}},
            )
            await ensure_index("dashboard_stats", [("user_id", ASCENDING)])
            await ensure_index(
                "user_features",
                [("user_id", ASCENDING), ("feature", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "user_id": {"$type": "string"},
                    "feature": {"$type": "string"},
                },
            )
            await ensure_index("user_features", [("user_id", ASCENDING), ("enabled", ASCENDING)])
            await ensure_index("bill_analyses", [("id", ASCENDING)], unique=True)
            await ensure_index("bill_analyses", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("bill_analyses", [("user_id", ASCENDING), ("provider", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("reports", [("id", ASCENDING)], unique=True)
            await ensure_index("reports", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("budget_events", [("id", ASCENDING)], unique=True)
            await ensure_index("budget_events", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index(
                "budget_events",
                [("user_id", ASCENDING), ("scope", ASCENDING), ("integration_id", ASCENDING), ("created_at", DESCENDING)]
            )

            await ensure_index(
                "waste_distribution",
                [("integration_id", ASCENDING), ("category_name", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "integration_id": {"$type": "string"},
                    "category_name": {"$type": "string"},
                },
            )
            await ensure_index("agent_notifications", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("recommendation_ledger", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "recommendation_ledger",
                [("user_id", ASCENDING), ("integration_id", ASCENDING), ("state", ASCENDING)],
            )
            await ensure_index(
                "recommendation_ledger",
                [("user_id", ASCENDING), ("provider_agreement_status", ASCENDING)],
            )
            await ensure_index(
                "recommendation_ledger",
                [("user_id", ASCENDING), ("ai_enrichment_status", ASCENDING), ("updated_at", DESCENDING)],
            )
            await ensure_index(
                "recommendation_evidence",
                [("user_id", ASCENDING), ("recommendation_id", ASCENDING)],
            )
            await ensure_index(
                "recommendation_state_events",
                [("user_id", ASCENDING), ("recommendation_id", ASCENDING), ("created_at", DESCENDING)],
            )
            await ensure_index("recommendation_ai_jobs", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "recommendation_ai_jobs",
                [("user_id", ASCENDING), ("status", ASCENDING), ("priority", DESCENDING), ("queued_at", ASCENDING)],
            )
            await ensure_index(
                "recommendation_ai_jobs",
                [("user_id", ASCENDING), ("recommendation_id", ASCENDING), ("status", ASCENDING)],
            )
            await ensure_index("recommendation_ai_enrichments", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "recommendation_ai_enrichments",
                [("user_id", ASCENDING), ("recommendation_id", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "user_id": {"$type": "string"},
                    "recommendation_id": {"$type": "string"},
                },
            )
            await ensure_index("provider_recommendations", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "provider_recommendations",
                [("user_id", ASCENDING), ("integration_id", ASCENDING), ("source_system", ASCENDING)],
            )
            await ensure_index("recommendation_savings_verifications", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "recommendation_savings_verifications",
                [("user_id", ASCENDING), ("recommendation_id", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "user_id": {"$type": "string"},
                    "recommendation_id": {"$type": "string"},
                },
            )
            await ensure_index(
                "recommendation_savings_verifications",
                [("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
            )
            await ensure_index("resource_cost_snapshots", [("id", ASCENDING)], unique=True)
            await ensure_index(
                "resource_cost_snapshots",
                [("user_id", ASCENDING), ("integration_id", ASCENDING), ("cloud_resource_id", ASCENDING), ("observed_at", DESCENDING)],
            )
            await ensure_index(
                "resource_cost_snapshots",
                [("user_id", ASCENDING), ("integration_id", ASCENDING), ("observed_at", DESCENDING)],
            )
            await ensure_index("reports", [("id", ASCENDING)], unique=True)
            await ensure_index("reports", [("user_id", ASCENDING), ("created_at", DESCENDING)])
            await ensure_index("governance_policies", [("user_id", ASCENDING), ("name", ASCENDING)], unique=True)
            await ensure_index("resources", [("user_id", ASCENDING), ("integration_id", ASCENDING)])
            await ensure_index("policy_violations", [("user_id", ASCENDING), ("status", ASCENDING)])
            await ensure_index(
                "daily_spend_history",
                [("integration_id", ASCENDING), ("spend_date", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "integration_id": {"$type": "string"},
                    "spend_date": {"$type": "string"},
                },
            )

            await ensure_index("resource_exclusions", [("id", ASCENDING)], unique=True)
            await ensure_index("resource_exclusions", [("user_id", ASCENDING), ("is_active", ASCENDING)])
            await ensure_index(
                "resource_exclusions",
                [("user_id", ASCENDING), ("cloud_resource_id", ASCENDING), ("integration_id", ASCENDING)],
                partialFilterExpression={
                    "cloud_resource_id": {"$type": "string"},
                    "integration_id": {"$type": "string"},
                },
            )
            await ensure_index("exclusion_suggestions", [("id", ASCENDING)], unique=True)
            await ensure_index("exclusion_suggestions", [("user_id", ASCENDING), ("status", ASCENDING)])
        except Exception as error:
            logger.warning("Mongo index bootstrap skipped or failed: %s", error)

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            self._indexes_ready = False

    def _prepare_document(
        self,
        table: str,
        row: Dict[str, Any],
        *,
        assign_created_at: bool = True,
    ) -> Dict[str, Any]:
        doc = _deep_serialize(dict(row))

        if table in {"resources", "cloud_integrations", "cloud_price_catalog", "cloud_price_catalog_syncs"}:
            doc["provider"] = _normalize_provider(doc.get("provider"))

        if not doc.get("id"):
            doc["id"] = str(uuid4())

        if assign_created_at and not doc.get("created_at"):
            doc["created_at"] = _utc_now_iso()

        return doc

    def _resolve_upsert_filter(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        if (
            table == "resources"
            and row.get("user_id")
            and row.get("integration_id")
            and row.get("cloud_resource_id")
        ):
            return {
                "user_id": row["user_id"],
                "integration_id": row["integration_id"],
                "cloud_resource_id": row["cloud_resource_id"],
            }

        if table == "governance_policies" and row.get("user_id") and row.get("name"):
            return {"user_id": row["user_id"], "name": row["name"]}

        if table == "dashboard_stats" and row.get("user_id") and row.get("integration_id"):
            return {"user_id": row["user_id"], "integration_id": row["integration_id"]}

        if table == "daily_spend_history" and row.get("user_id") and row.get("integration_id") and row.get("spend_date"):
            return {
                "user_id": row["user_id"],
                "integration_id": row["integration_id"],
                "spend_date": row["spend_date"],
            }

        if table == "waste_distribution" and row.get("user_id") and row.get("integration_id") and row.get("category_name"):
            return {
                "user_id": row["user_id"],
                "integration_id": row["integration_id"],
                "category_name": row["category_name"],
            }

        if table == "user_features" and row.get("user_id") and row.get("feature"):
            return {"user_id": row["user_id"], "feature": row["feature"]}

        if table == "cloud_price_catalog" and row.get("provider") and row.get("catalog_key"):
            return {"provider": row["provider"], "catalog_key": row["catalog_key"]}

        if table == "cloud_price_catalog_syncs" and row.get("provider") and row.get("source"):
            return {
                "provider": row["provider"],
                "source": row["source"],
                "service_code": row.get("service_code"),
                "region": row.get("region"),
            }

        if row.get("id"):
            return {"id": row["id"]}

        return row

    @staticmethod
    def _resource_cost_source_rank(row: Dict[str, Any]) -> int:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        source = str(metadata.get("cost_source") or "").strip().lower()
        cost = _to_float(row.get("cost"))

        if source == "actual":
            return 4
        if cost > 0:
            return 3
        if source in {"no_direct_charge", "included", "free"}:
            return 2
        if source == "billing_unavailable":
            return 1
        return 0

    @staticmethod
    def _resource_time_value(row: Dict[str, Any]) -> str:
        return str(row.get("updated_at") or row.get("last_scanned_at") or row.get("created_at") or "")

    def _resource_quality_key(self, row: Dict[str, Any]) -> Tuple[int, float, str]:
        return (
            self._resource_cost_source_rank(row),
            _to_float(row.get("cost")),
            self._resource_time_value(row),
        )

    def _choose_resource_candidate(
        self,
        current: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._resource_quality_key(candidate) >= self._resource_quality_key(current):
            winner = dict(candidate)
            loser = current
        else:
            winner = dict(current)
            loser = candidate

        winner_metadata = {
            **(loser.get("metadata") if isinstance(loser.get("metadata"), dict) else {}),
            **(winner.get("metadata") if isinstance(winner.get("metadata"), dict) else {}),
        }
        winner_tags = {
            **(loser.get("tags") if isinstance(loser.get("tags"), dict) else {}),
            **(winner.get("tags") if isinstance(winner.get("tags"), dict) else {}),
        }
        winner["metadata"] = winner_metadata
        winner["tags"] = winner_tags
        return winner

    # =========================================================================
    # GENERIC OPERATIONS
    # =========================================================================

    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        collection = await self._collection(table)
        projection = _projection_from_columns(columns)
        cursor = collection.find(filters or {}, projection=projection)
        if limit is not None:
            cursor = cursor.limit(limit)
        docs = await cursor.to_list(length=limit or 5000)
        return [_strip_mongo_id(doc) for doc in docs]

    async def insert(
        self,
        table: str,
        data: List[Dict[str, Any]] | Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        collection = await self._collection(table)
        rows = data if isinstance(data, list) else [data]
        payload = [self._prepare_document(table, row) for row in rows]
        if not payload:
            return []

        try:
            await collection.insert_many(payload, ordered=False)
            return payload
        except Exception as error:
            logger.error("insert DB Error (%s): %s", table, error)
            logger.error("First 2 rows: %s", str(payload[:2])[:1000])
            raise

    async def upsert(
        self,
        table: str,
        data: List[Dict[str, Any]] | Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        collection = await self._collection(table)
        rows = data if isinstance(data, list) else [data]
        if not rows:
            return []

        now = _utc_now_iso()
        results: List[Dict[str, Any]] = []
        for row in rows:
            prepared = self._prepare_document(table, row)
            filters = self._resolve_upsert_filter(table, prepared)
            set_payload = {**prepared, "updated_at": now}
            set_payload.pop("id", None)
            set_payload.pop("created_at", None)
            update_doc = {
                "$set": set_payload,
                "$setOnInsert": {
                    "id": prepared["id"],
                    "created_at": prepared.get("created_at", now),
                },
            }
            await collection.update_one(filters, update_doc, upsert=True)
            current = await collection.find_one(filters)
            if current:
                results.append(_strip_mongo_id(current))
        return results

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        collection = await self._collection(table)
        update_payload = _deep_serialize(dict(data))
        update_payload["updated_at"] = _utc_now_iso()

        try:
            await collection.update_many(filters, {"$set": update_payload})
            docs = await collection.find(filters).to_list(length=None)
            return [_strip_mongo_id(doc) for doc in docs]
        except Exception as error:
            logger.error("update DB Error (%s): %s", table, error)
            logger.error("Data: %s", str(update_payload)[:1000])
            raise

    async def delete(self, table: str, filters: Dict[str, Any]) -> bool:
        collection = await self._collection(table)
        await collection.delete_many(filters or {})
        return True

    # =========================================================================
    # CLOUD INTEGRATIONS
    # =========================================================================

    async def get_integration(
        self,
        integration_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        results = await self.select(
            "cloud_integrations",
            filters={"id": integration_id, "user_id": user_id},
        )
        return results[0] if results else None

    async def get_user_integrations(self, user_id: str) -> List[Dict[str, Any]]:
        return await self.select("cloud_integrations", filters={"user_id": user_id})

    async def update_integration(
        self,
        integration_id: str,
        user_id: str,
        data: Dict[str, Any],
    ) -> bool:
        await self.update("cloud_integrations", data, {"id": integration_id, "user_id": user_id})
        return True

    async def update_integration_last_scan(self, integration_id: str, user_id: str) -> None:
        await self.update(
            "cloud_integrations",
            {"last_scan": _utc_now_iso()},
            {"id": integration_id, "user_id": user_id},
        )

    # =========================================================================
    # RESOURCES
    # =========================================================================

    async def get_resources(
        self,
        user_id: str,
        integration_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {"user_id": user_id}
        if integration_id:
            filters["integration_id"] = integration_id
        return await self.select("resources", filters=filters)

    async def upsert_resources(self, resources: List[Dict[str, Any]]) -> bool:
        if not resources:
            return True
        await self.upsert("resources", resources)
        return True

    async def upsert_resource(self, resource_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        normalized_data = normalize_resource_row(resource_data)
        normalized_data["provider"] = _normalize_provider(normalized_data.get("provider"))
        result = await self.upsert("resources", normalized_data)
        return result[0] if result else None

    async def bulk_upsert_resources(
        self,
        resources: List[Dict[str, Any]],
        batch_size: int = 50,
    ) -> int:
        if not resources:
            return 0

        normalized_resources = normalize_resource_batch(resources)

        deduped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        affected_scopes: set[Tuple[str, str]] = set()
        for row in normalized_resources:
            user_id = str(row.get("user_id", "")).strip()
            integration_id = str(row.get("integration_id", "")).strip()
            cloud_resource_id = str(row.get("cloud_resource_id", "")).strip()
            if not user_id or not integration_id or not cloud_resource_id:
                continue

            prepared = self._prepare_document("resources", row)
            prepared["provider"] = _normalize_provider(prepared.get("provider"))
            key = (user_id, integration_id, cloud_resource_id)
            affected_scopes.add((user_id, integration_id))
            existing = deduped.get(key)
            deduped[key] = (
                self._choose_resource_candidate(existing, prepared)
                if existing else prepared
            )

        deduped_resources = list(deduped.values())
        if not deduped_resources:
            return 0

        collection = await self._collection("resources")
        success_count = 0

        for index in range(0, len(deduped_resources), batch_size):
            batch = deduped_resources[index:index + batch_size]
            operations: List[UpdateOne] = []

            for row in batch:
                now = _utc_now_iso()
                filters = {
                    "user_id": row["user_id"],
                    "integration_id": row["integration_id"],
                    "cloud_resource_id": row["cloud_resource_id"],
                }
                set_payload = {**row, "updated_at": now}
                set_payload.pop("id", None)
                set_payload.pop("created_at", None)
                update_doc = {
                    "$set": set_payload,
                    "$setOnInsert": {
                        "id": row["id"],
                        "created_at": row.get("created_at", now),
                    },
                }
                operations.append(UpdateOne(filters, update_doc, upsert=True))

            try:
                await collection.bulk_write(operations, ordered=False)
                success_count += len(batch)
                logger.debug(
                    "Upserted batch %s: %s resources",
                    index // batch_size + 1,
                    len(batch),
                )
            except Exception as error:
                logger.error("Failed to upsert batch %s: %s", index // batch_size + 1, error)
                first_row_keys = list(batch[0].keys()) if batch else []
                logger.error("First row keys: %s", first_row_keys)
                logger.error("First 2 rows: %s", str(batch[:2])[:1000])

        logger.info("Bulk upsert complete: %s/%s resources", success_count, len(deduped_resources))
        for user_id, integration_id in affected_scopes:
            try:
                removed = await self.dedupe_resources_for_integration(user_id, integration_id)
                if removed:
                    logger.info(
                        "Removed %s duplicate resources for integration %s",
                        removed,
                        integration_id,
                    )
            except Exception as error:
                logger.warning(
                    "Resource duplicate cleanup skipped for integration %s: %s",
                    integration_id,
                    error,
                )
        return success_count

    async def dedupe_resources_for_integration(
        self,
        user_id: str,
        integration_id: str,
    ) -> int:
        normalized_user_id = str(user_id or "").strip()
        normalized_integration_id = str(integration_id or "").strip()
        if not normalized_user_id or not normalized_integration_id:
            return 0

        collection = await self._collection("resources")
        filters = {"user_id": normalized_user_id, "integration_id": normalized_integration_id}
        cursor = collection.find(filters)
        documents = await cursor.to_list(length=None)
        if not documents:
            return 0

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for document in documents:
            row = _strip_mongo_id(document)
            normalized = normalize_resource_row(row)
            normalized["id"] = row.get("id") or normalized.get("id")
            normalized["created_at"] = row.get("created_at")
            normalized["updated_at"] = row.get("updated_at")
            normalized["last_scanned_at"] = row.get("last_scanned_at")
            normalized["_stored_cloud_resource_id"] = row.get("cloud_resource_id")
            cloud_resource_id = str(normalized.get("cloud_resource_id") or "").strip()
            if not cloud_resource_id:
                continue
            grouped.setdefault(cloud_resource_id, []).append(normalized)

        removed_count = 0
        now = _utc_now_iso()
        for cloud_resource_id, rows in grouped.items():
            survivor = rows[0]
            for candidate in rows[1:]:
                survivor = self._choose_resource_candidate(survivor, candidate)

            survivor_id = str(survivor.get("id") or "").strip()
            if not survivor_id:
                continue

            duplicate_ids = [
                str(row.get("id"))
                for row in rows
                if str(row.get("id") or "").strip()
                and str(row.get("id")) != survivor_id
            ]
            stored_ids = {
                str(row.get("_stored_cloud_resource_id") or "").strip()
                for row in rows
            }
            needs_canonical_update = len(rows) > 1 or stored_ids != {cloud_resource_id}
            if not needs_canonical_update:
                continue

            if duplicate_ids:
                result = await collection.delete_many(
                    {
                        "user_id": normalized_user_id,
                        "integration_id": normalized_integration_id,
                        "id": {"$in": duplicate_ids},
                    }
                )
                removed_count += int(getattr(result, "deleted_count", 0) or 0)

            update_payload = {
                **survivor,
                "cloud_resource_id": cloud_resource_id,
                "updated_at": now,
            }
            update_payload.pop("id", None)
            update_payload.pop("created_at", None)
            update_payload.pop("_stored_cloud_resource_id", None)

            await collection.update_one(
                {
                    "user_id": normalized_user_id,
                    "integration_id": normalized_integration_id,
                    "id": survivor_id,
                },
                {"$set": update_payload},
                upsert=False,
            )

        return removed_count

    async def delete_resources_for_integration(
        self,
        user_id: str,
        integration_id: str,
        exclude_batch_id: Optional[str] = None,
    ) -> bool:
        try:
            filters: Dict[str, Any] = {"integration_id": integration_id, "user_id": user_id}
            if exclude_batch_id:
                filters["scan_batch_id"] = {"$ne": exclude_batch_id}
            await self.delete("resources", filters)
            return True
        except Exception as error:
            logger.error("Failed to delete resources for integration %s: %s", integration_id, error)
            return False

    # =========================================================================
    # SCAN HISTORY
    # =========================================================================

    async def create_scan_history(
        self,
        user_id: str,
        integration_id: str,
    ) -> Optional[str]:
        try:
            result = await self.insert(
                "scan_history",
                {
                    "user_id": user_id,
                    "integration_id": integration_id,
                    "status": "running",
                    "started_at": _utc_now_iso(),
                    "total_resources": 0,
                    "waste_found": 0,
                    "total_savings": 0.0,
                },
            )
            if result:
                scan_id = result[0].get("id")
                logger.info("Created scan_history record: %s", scan_id)
                return scan_id
            return None
        except Exception as error:
            logger.error("Failed to create scan_history: %s", error)
            return None

    async def complete_scan_history(
        self,
        scan_id: str,
        total_resources: int,
        waste_found: int,
        total_savings: float,
        scan_metadata: Optional[Dict[str, Any]] = None,
        governance_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            update_data: Dict[str, Any] = {
                "status": "completed",
                "completed_at": _utc_now_iso(),
                "total_resources": total_resources,
                "waste_found": waste_found,
                "total_savings": total_savings,
            }
            if scan_metadata:
                update_data["scan_metadata"] = scan_metadata
            if governance_data:
                update_data["governance_data"] = governance_data

            await self.update("scan_history", update_data, {"id": scan_id})
            logger.info(
                "Completed scan_history %s: %s resources, $%.2f savings",
                scan_id,
                total_resources,
                total_savings,
            )
        except Exception as error:
            logger.error("Failed to complete scan_history %s: %s", scan_id, error)

    async def fail_scan_history(
        self,
        scan_id: str,
        error_message: str,
    ) -> None:
        try:
            await self.update(
                "scan_history",
                {
                    "status": "failed",
                    "completed_at": _utc_now_iso(),
                    "error_message": error_message[:1000],
                },
                {"id": scan_id},
            )
            logger.warning("Failed scan_history %s: %s", scan_id, error_message)
        except Exception as error:
            logger.error("Failed to update scan_history failure: %s", error)

    # =========================================================================
    # DASHBOARD STATS
    # =========================================================================

    async def get_dashboard_stats(
        self,
        user_id: str,
        integration_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        filters: Dict[str, Any] = {"user_id": user_id}
        if integration_id:
            filters["integration_id"] = integration_id

        results = await self.select("dashboard_stats", filters=filters)
        if not results:
            return None
        if integration_id:
            return results[0]

        confidence_values = [
            _to_float(row.get("ai_confidence_score"))
            for row in results
            if row.get("ai_confidence_score") is not None
        ]
        average_confidence = (
            int(round(sum(confidence_values) / len(confidence_values)))
            if confidence_values else 0
        )

        return {
            "user_id": user_id,
            "total_spend": round(sum(_to_float(row.get("total_spend")) for row in results), 2),
            "potential_savings": round(sum(_to_float(row.get("potential_savings")) for row in results), 2),
            "active_resources_count": int(sum(_to_float(row.get("active_resources_count")) for row in results)),
            "ai_confidence_score": average_confidence,
            "carbon_footprint_kg": round(sum(_to_float(row.get("carbon_footprint_kg")) for row in results), 2),
            "cost_of_inaction_6mo": round(sum(_to_float(row.get("cost_of_inaction_6mo")) for row in results), 2),
        }

    async def upsert_dashboard_stats(self, stats: Dict[str, Any]) -> bool:
        collection = await self._collection("dashboard_stats")
        doc = self._prepare_document("dashboard_stats", stats)
        if stats.get("user_id") and stats.get("integration_id"):
            await collection.replace_one(
                {"user_id": stats["user_id"], "integration_id": stats["integration_id"]},
                doc,
                upsert=True,
            )
        else:
            await collection.insert_one(doc)
        return True

    async def update_dashboard_stats(
        self,
        user_id: str,
        integration_id: str,
        stats: Dict[str, Any],
    ) -> None:
        try:
            try:
                await self.delete("dashboard_stats", {"user_id": user_id, "integration_id": integration_id})
            except Exception:
                pass

            await self.insert(
                "dashboard_stats",
                {
                    "user_id": user_id,
                    "integration_id": integration_id,
                    **stats,
                },
            )
            logger.info("Updated dashboard_stats for integration %s", integration_id)
        except Exception as error:
            logger.error("Failed to update dashboard_stats: %s", error)

    # =========================================================================
    # USER FEATURES
    # =========================================================================

    async def mark_user_feature_enabled(
        self,
        user_id: str,
        feature: str,
        *,
        last_used: Optional[str] = None,
        first_upload_at: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        collection = await self._collection("user_features")
        safe_feature = str(feature or "").strip()
        if not user_id or not safe_feature:
            return None

        now_iso = last_used or _utc_now_iso()
        filters = {"user_id": user_id, "feature": safe_feature}
        existing = await collection.find_one(filters)
        first_seen = str(
            (existing or {}).get("first_upload_at")
            or first_upload_at
            or now_iso
        )
        feature_id = str((existing or {}).get("id") or uuid4())

        await collection.update_one(
            filters,
            {
                "$set": {
                    "user_id": user_id,
                    "feature": safe_feature,
                    "enabled": True,
                    "last_used": now_iso,
                    "first_upload_at": first_seen,
                    "updated_at": now_iso,
                },
                "$setOnInsert": {
                    "id": feature_id,
                    "created_at": now_iso,
                },
            },
            upsert=True,
        )

        current = await collection.find_one(filters)
        return _strip_mongo_id(current) if current else None

    async def get_user_features(self, user_id: str) -> List[Dict[str, Any]]:
        collection = await self._collection("user_features")
        documents = await collection.find(
            {"user_id": user_id, "enabled": True}
        ).sort("feature", ASCENDING).to_list(length=None)
        return [_strip_mongo_id(document) for document in documents]

    # =========================================================================
    # BILL ANALYSES
    # =========================================================================

    async def create_bill_analysis(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        inserted = await self.insert("bill_analyses", analysis)
        return inserted[0] if inserted else None

    async def get_bill_analysis(
        self,
        user_id: str,
        analysis_id: str,
    ) -> Optional[Dict[str, Any]]:
        collection = await self._collection("bill_analyses")
        document = await collection.find_one({"id": analysis_id, "user_id": user_id})
        return _strip_mongo_id(document) if document else None

    async def get_bill_analyses(
        self,
        user_id: str,
        *,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        collection = await self._collection("bill_analyses")
        safe_limit = max(1, min(limit, 50))
        cursor = collection.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(safe_limit)
        documents = await cursor.to_list(length=safe_limit)
        return [_strip_mongo_id(document) for document in documents]

    async def get_latest_bill_analysis(self, user_id: str) -> Optional[Dict[str, Any]]:
        collection = await self._collection("bill_analyses")
        documents = await collection.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(1).to_list(length=1)
        return _strip_mongo_id(documents[0]) if documents else None

    # =========================================================================
    # WASTE DISTRIBUTION
    # =========================================================================

    async def upsert_waste_distribution(
        self,
        waste_data: List[Dict[str, Any]],
    ) -> bool:
        if not waste_data:
            return True

        if waste_data[0].get("user_id") and waste_data[0].get("integration_id"):
            try:
                await self.delete(
                    "waste_distribution",
                    {
                        "user_id": waste_data[0]["user_id"],
                        "integration_id": waste_data[0]["integration_id"],
                    },
                )
            except Exception:
                pass

        await self.insert("waste_distribution", waste_data)
        return True

    async def update_waste_distribution(
        self,
        user_id: str,
        integration_id: str,
        distribution: List[Dict[str, Any]],
    ) -> None:
        try:
            try:
                await self.delete("waste_distribution", {"user_id": user_id, "integration_id": integration_id})
            except Exception:
                pass

            if distribution:
                rows = [
                    {
                        "user_id": user_id,
                        "integration_id": integration_id,
                        "category_name": item["category_name"],
                        "value": item["value"],
                    }
                    for item in distribution
                ]
                await self.insert("waste_distribution", rows)
                logger.info(
                    "Updated waste_distribution for integration %s: %s categories",
                    integration_id,
                    len(rows),
                )
        except Exception as error:
            logger.error("Failed to update waste_distribution: %s", error)

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    async def create_notifications(
        self,
        notifications: List[Dict[str, Any]],
    ) -> bool:
        if not notifications:
            return True
        await self.insert("agent_notifications", notifications)
        return True

    async def create_agent_notification(
        self,
        user_id: str,
        resource_id: str,
        notification_type: str,
        recommendation: str,
    ) -> None:
        try:
            await self.insert(
                "agent_notifications",
                {
                    "user_id": user_id,
                    "resource_id": resource_id,
                    "type": notification_type,
                    "status": "pending",
                    "recommendation": recommendation,
                    "action": "review",
                },
            )
            logger.debug("Created notification for resource %s", resource_id)
        except Exception as error:
            logger.error("Failed to create agent notification: %s", error)

    async def get_notifications(
        self,
        user_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {"user_id": user_id}
        if status:
            filters["status"] = status
        return await self.select("agent_notifications", filters=filters)

    async def create_budget_event(
        self,
        event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        result = await self.insert("budget_events", event)
        return result[0] if result else None

    async def get_budget_events(
        self,
        user_id: str,
        *,
        scope: Optional[str] = None,
        integration_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        collection = await self._collection("budget_events")
        filters: Dict[str, Any] = {"user_id": user_id}
        if scope:
            filters["scope"] = scope
        if integration_id:
            filters["integration_id"] = integration_id

        cursor = collection.find(filters).sort("created_at", DESCENDING).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_strip_mongo_id(doc) for doc in docs]

    async def get_latest_budget_event(
        self,
        *,
        user_id: str,
        scope: str,
        integration_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        events = await self.get_budget_events(
            user_id,
            scope=scope,
            integration_id=integration_id,
            limit=1,
        )
        return events[0] if events else None

    # =========================================================================
    # GOVERNANCE POLICIES
    # =========================================================================

    async def upsert_governance_policy(
        self,
        user_id: str,
        name: str,
        description: str,
        policy_type: str,
        compliance_rate: int,
        violations: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            existing = await self.select("governance_policies", filters={"user_id": user_id, "name": name})
            policy_data = {
                "user_id": user_id,
                "name": name,
                "description": description,
                "policy_type": policy_type,
                "is_active": True,
                "compliance_rate": compliance_rate,
                "violations": violations,
                "status": "active" if violations == 0 else "violations_found",
                "metadata": metadata or {},
            }

            if existing:
                await self.update("governance_policies", policy_data, {"id": existing[0]["id"]})
                return existing[0]

            result = await self.insert("governance_policies", policy_data)
            return result[0] if result else None
        except Exception as error:
            logger.error("Failed to upsert governance policy '%s': %s", name, error)
            return None

    async def upsert_policy_violation(
        self,
        policy_id: str,
        resource_id: str,
        user_id: str,
        violation_detail: str,
        severity: str = "medium",
    ) -> None:
        try:
            await self.insert(
                "policy_violations",
                {
                    "policy_id": policy_id,
                    "resource_id": resource_id,
                    "user_id": user_id,
                    "violation_details": {"detail": violation_detail},
                    "severity": severity,
                    "status": "active",
                },
            )
        except Exception as error:
            logger.error("Failed to insert policy violation: %s", error)

    async def clear_policy_violations(
        self,
        user_id: str,
        policy_id: Optional[str] = None,
    ) -> None:
        try:
            filters: Dict[str, Any] = {"user_id": user_id, "status": "active"}
            if policy_id:
                filters["policy_id"] = policy_id
            await self.delete("policy_violations", filters)
        except Exception as error:
            logger.debug("Could not clear policy violations: %s", error)

    async def get_resources_for_integration(self, user_id: str, integration_id: str) -> List[Dict[str, Any]]:
        return await self.select("resources", filters={"user_id": user_id, "integration_id": integration_id})

    # =========================================================================
    # DAILY SPEND HISTORY
    # =========================================================================

    async def save_daily_spend_history(
        self,
        user_id: str,
        integration_id: str,
        daily_totals: List[Dict[str, Any]],
        service_breakdown: Optional[Dict[str, float]] = None,
        currency: str = "USD",
    ) -> None:
        if not daily_totals:
            logger.debug("No daily spend data to save")
            return

        normalized_user_id = str(user_id or "").strip()
        normalized_integration_id = str(integration_id or "").strip()
        if not normalized_user_id or not normalized_integration_id:
            logger.error(
                "Refusing to save daily spend history without user_id/integration_id (user_id=%s, integration_id=%s)",
                normalized_user_id,
                normalized_integration_id,
            )
            return

        try:
            collection = await self._collection("daily_spend_history")
            # Atomic: delete old rows then insert new ones in a single try block
            await collection.delete_many(
                {"user_id": normalized_user_id, "integration_id": normalized_integration_id}
            )

            rows = []
            for day in daily_totals:
                rows.append(
                    {
                        "user_id": normalized_user_id,
                        "integration_id": normalized_integration_id,
                        "spend_date": day["date"],
                        "amount": round(day["amount"], 4),
                        "currency": currency,
                        "service_breakdown": service_breakdown or {},
                    }
                )

            if rows:
                await collection.insert_many(rows, ordered=False)
                logger.info(
                    "Saved %s daily spend records for integration %s",
                    len(rows),
                    normalized_integration_id,
                )
        except Exception as error:
            logger.error("Failed to save daily spend history: %s", error)

    async def get_daily_spend_history(
        self,
        user_id: str,
        integration_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        try:
            filters: Dict[str, Any] = {"user_id": user_id}
            if integration_id:
                filters["integration_id"] = integration_id
            else:
                filters["integration_id"] = {"$type": "string", "$ne": ""}

            results = await self.select("daily_spend_history", filters=filters)
            aggregated = aggregate_daily_spend_rows(results)
            return aggregated[-days:] if len(aggregated) > days else aggregated
        except Exception as error:
            logger.error("Failed to get daily spend history: %s", error)
            return []

    # =========================================================================
    # INTEGRATION HEALTH (BATCH)
    # =========================================================================

    async def get_user_integrations_health_batch(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Return health telemetry for ALL integrations owned by user_id.
        Uses one aggregation per collection — not one query per integration.

        Each row in the returned list has:
            integration:       cloud_integrations doc
            last_scan:         most-recent scan_history row (any status), or None
            last_success_scan: most-recent completed scan_history row, or None
            ai_counts:         {"queued", "running", "enriched", "failed",
                                "last_success_at"}
        """
        try:
            integrations = await self.select(
                "cloud_integrations",
                filters={"user_id": user_id},
            )
            if not integrations:
                return []

            integration_ids = [ig["id"] for ig in integrations if ig.get("id")]

            # _collection() used directly: aggregation pipelines can't go through select()
            scan_col = await self._collection("scan_history")
            attempt_pipeline = [
                {"$match": {"user_id": user_id, "integration_id": {"$in": integration_ids}}},
                {"$sort": {"started_at": DESCENDING}},
                {"$group": {
                    "_id": "$integration_id",
                    "status": {"$first": "$status"},
                    "started_at": {"$first": "$started_at"},
                    "completed_at": {"$first": "$completed_at"},
                    "total_resources": {"$first": "$total_resources"},
                    "error_message": {"$first": "$error_message"},
                }},
            ]
            last_scan_by_id: Dict[str, Dict[str, Any]] = {}
            async for doc in scan_col.aggregate(attempt_pipeline):
                iid = str(doc.get("_id") or "")
                if iid:
                    last_scan_by_id[iid] = {k: v for k, v in doc.items() if k != "_id"}

            # Most-recent *successful* scan per integration
            success_pipeline = [
                {"$match": {
                    "user_id": user_id,
                    "integration_id": {"$in": integration_ids},
                    "status": "completed",
                }},
                {"$sort": {"completed_at": DESCENDING}},
                {"$group": {
                    "_id": "$integration_id",
                    "completed_at": {"$first": "$completed_at"},
                    "started_at": {"$first": "$started_at"},
                    "total_resources": {"$first": "$total_resources"},
                }},
            ]
            last_success_by_id: Dict[str, Dict[str, Any]] = {}
            async for doc in scan_col.aggregate(success_pipeline):
                iid = str(doc.get("_id") or "")
                if iid:
                    last_success_by_id[iid] = {k: v for k, v in doc.items() if k != "_id"}

            # AI enrichment counts per integration
            rec_col = await self._collection("recommendation_ledger")
            ai_pipeline = [
                {"$match": {"user_id": user_id, "integration_id": {"$in": integration_ids}}},
                {"$group": {
                    "_id": "$integration_id",
                    "queued": {"$sum": {"$cond": [{"$eq": ["$ai_enrichment_status", "queued"]}, 1, 0]}},
                    "running": {"$sum": {"$cond": [{"$eq": ["$ai_enrichment_status", "running"]}, 1, 0]}},
                    "enriched": {"$sum": {"$cond": [
                        {"$in": ["$ai_enrichment_status", ["enriched", "not_required"]]}, 1, 0,
                    ]}},
                    "failed": {"$sum": {"$cond": [{"$eq": ["$ai_enrichment_status", "failed"]}, 1, 0]}},
                    "last_success_at": {"$max": "$ai_enriched_at"},
                }},
            ]
            ai_by_id: Dict[str, Dict[str, Any]] = {}
            async for doc in rec_col.aggregate(ai_pipeline):
                iid = str(doc.get("_id") or "")
                if iid:
                    ai_by_id[iid] = {k: v for k, v in doc.items() if k != "_id"}

            _empty_ai: Dict[str, Any] = {
                "queued": 0, "running": 0, "enriched": 0, "failed": 0, "last_success_at": None,
            }
            return [
                {
                    "integration": ig,
                    "last_scan": last_scan_by_id.get(ig.get("id") or ""),
                    "last_success_scan": last_success_by_id.get(ig.get("id") or ""),
                    "ai_counts": ai_by_id.get(ig.get("id") or "", _empty_ai),
                }
                for ig in integrations
            ]

        except Exception as error:
            logger.error("get_user_integrations_health_batch failed: %s", error)
            return []


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_client: Optional[MongoDBClient] = None


def get_db_client() -> MongoDBClient:
    """Get MongoDB database client instance."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoDBClient(
            mongodb_uri=settings.mongodb_uri,
            database_name=settings.mongodb_db_name,
        )
    return _client
