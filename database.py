"""
database.py — Async MongoDB (Motor) layer for Webify Bot.

Collections
-----------
users    : telegram_id, username, tier, joined_at, custom_domain_prefix (+ is_banned)
sites    : site_id, owner_id, slug, site_name, file_path, custom_domain,
           is_locked, views_count, created_at (+ size_bytes, updated_at)
qr_codes : qr_id, site_id, style_type, created_at
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import OperationFailure

import config

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    """Thin wrapper around Motor with all CRUD helpers used by the bot."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #
    async def connect(self) -> None:
        self.client = AsyncIOMotorClient(
            config.MONGO_URI, serverSelectionTimeoutMS=15000, tz_aware=True
        )
        self.db = self.client[config.DB_NAME]
        await self.client.admin.command("ping")
        await self._ensure_indexes()
        log.info("MongoDB connected (db=%s)", config.DB_NAME)

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None

    async def _ensure_indexes(self) -> None:
        """
        Create indexes. Unique indexes are *partial* (only documents whose key has the
        right BSON type are indexed), so leftover documents from an older schema or
        another app sharing this database (missing/null keys) can't break startup.
        """
        assert self.db is not None
        str_key = lambda f: {f: {"$type": "string"}}
        num_key = {"telegram_id": {"$type": ["int", "long"]}}
        specs = [
            (self.db.users, "telegram_id", dict(unique=True, partialFilterExpression=num_key)),
            (self.db.users, "username", {}),
            (self.db.sites, "site_id", dict(unique=True, partialFilterExpression=str_key("site_id"))),
            (self.db.sites, "slug", dict(unique=True, partialFilterExpression=str_key("slug"))),
            (self.db.sites, [("owner_id", ASCENDING), ("created_at", DESCENDING)], {}),
            # Unique custom domains, but many sites may have an empty one.
            (self.db.sites, "custom_domain",
             dict(unique=True, partialFilterExpression={"custom_domain": {"$gt": ""}})),
            (self.db.qr_codes, "qr_id", dict(unique=True, partialFilterExpression=str_key("qr_id"))),
            (self.db.qr_codes, "site_id", {}),
        ]
        await self._drop_foreign_unique_indexes(specs)
        for collection, keys, options in specs:
            await self._create_index_safe(collection, keys, options)

    async def _drop_foreign_unique_indexes(self, specs) -> None:
        """
        Remove leftover *unique* indexes (e.g. ``uid_1`` from an older bot that used the
        same database) on our collections. They would reject our documents, which have no
        such field (every missing value counts as null -> E11000 on the second insert).
        Only indexes are dropped; documents are never touched.
        """
        wanted: dict[str, set[str]] = {}
        for collection, keys, _ in specs:
            wanted.setdefault(collection.name, set()).add(self._index_name(keys))
        for collection in (self.db.users, self.db.sites, self.db.qr_codes):  # type: ignore[union-attr]
            try:
                info = await collection.index_information()
            except OperationFailure as exc:
                log.warning("Could not inspect indexes of %s: %s", collection.name, exc)
                continue
            for name, spec in info.items():
                if name == "_id_" or name in wanted.get(collection.name, set()):
                    continue
                if spec.get("unique"):
                    log.warning("Dropping foreign unique index %s on %s (%s)",
                                name, collection.name, spec.get("key"))
                    try:
                        await collection.drop_index(name)
                    except OperationFailure as exc:
                        log.error("Could not drop index %s on %s: %s", name, collection.name, exc)

    @staticmethod
    def _index_name(keys) -> str:
        """MongoDB's auto-generated index name, e.g. 'slug_1' or 'owner_id_1_created_at_-1'."""
        pairs = [(keys, 1)] if isinstance(keys, str) else list(keys)
        return "_".join(f"{k}_{d}" for k, d in pairs)

    async def _create_index_safe(self, collection, keys, options: dict) -> None:
        """
        Create an index; if an older version of *our own* index with the same name but
        different options exists (code 85/86), drop it and recreate. Other failures are
        logged instead of crashing startup.
        """
        try:
            await collection.create_index(keys, **options)
            return
        except OperationFailure as exc:
            if exc.code not in (85, 86):          # IndexOptionsConflict / IndexKeySpecsConflict
                log.error(
                    "Could not create index %s on %s: %s. Fix or drop the conflicting "
                    "data, or set DB_NAME to a fresh database.", keys, collection.name, exc,
                )
                return
        name = self._index_name(keys)
        log.warning("Replacing outdated index %s on %s", name, collection.name)
        try:
            await collection.drop_index(name)
            await collection.create_index(keys, **options)
        except OperationFailure as exc:
            log.error(
                "Could not rebuild index %s on %s: %s. Fix or drop the conflicting "
                "data, or set DB_NAME to a fresh database.", keys, collection.name, exc,
            )

    @property
    def _users(self):
        return self.db.users  # type: ignore[union-attr]

    @property
    def _sites(self):
        return self.db.sites  # type: ignore[union-attr]

    @property
    def _qr(self):
        return self.db.qr_codes  # type: ignore[union-attr]

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #
    async def upsert_user(self, telegram_id: int, username: str = "") -> dict:
        """Create the user on first contact, refresh the username otherwise."""
        doc = await self._users.find_one_and_update(
            {"telegram_id": telegram_id},
            {
                "$set": {"username": username or ""},
                "$setOnInsert": {
                    "tier": "Free",
                    "joined_at": utcnow(),
                    "custom_domain_prefix": "",
                    "is_banned": False,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc

    async def get_user(self, telegram_id: int) -> Optional[dict]:
        return await self._users.find_one({"telegram_id": telegram_id})

    async def search_users(self, query: str, limit: int = 10) -> list[dict]:
        query = query.strip().lstrip("@")
        if not query:
            return []
        if query.isdigit():
            return await self._users.find({"telegram_id": int(query)}).to_list(limit)
        regex = {"$regex": re.escape(query), "$options": "i"}
        return await self._users.find({"username": regex}).limit(limit).to_list(limit)

    async def set_banned(self, telegram_id: int, banned: bool) -> None:
        await self._users.update_one({"telegram_id": telegram_id}, {"$set": {"is_banned": banned}})

    async def set_tier(self, telegram_id: int, tier: str) -> None:
        await self._users.update_one({"telegram_id": telegram_id}, {"$set": {"tier": tier}})

    async def set_domain_prefix(self, telegram_id: int, prefix: str) -> None:
        await self._users.update_one(
            {"telegram_id": telegram_id}, {"$set": {"custom_domain_prefix": prefix}}
        )

    async def count_users(self, query: Optional[dict] = None) -> int:
        return await self._users.count_documents(query or {})

    async def iter_user_ids(self) -> AsyncIterator[int]:
        """Yield the IDs of every non-banned user (used by the broadcast engine)."""
        cursor = self._users.find({"is_banned": {"$ne": True}}, {"telegram_id": 1})
        async for doc in cursor:
            yield doc["telegram_id"]

    # ------------------------------------------------------------------ #
    # Sites
    # ------------------------------------------------------------------ #
    async def create_site(
        self,
        *,
        site_id: str,
        owner_id: int,
        slug: str,
        site_name: str,
        file_path: str,
        size_bytes: int = 0,
    ) -> dict:
        now = utcnow()
        doc = {
            "site_id": site_id,
            "owner_id": owner_id,
            "slug": slug,
            "site_name": site_name,
            "file_path": file_path,
            "custom_domain": "",
            "is_locked": False,
            "views_count": 0,
            "created_at": now,
            "updated_at": now,
            "size_bytes": size_bytes,
        }
        await self._sites.insert_one(dict(doc))
        return doc

    async def get_site(self, site_id: str) -> Optional[dict]:
        return await self._sites.find_one({"site_id": site_id})

    async def get_site_by_slug(self, slug: str) -> Optional[dict]:
        return await self._sites.find_one({"slug": slug.lower()})

    async def get_site_by_domain(self, domain: str) -> Optional[dict]:
        if not domain:
            return None
        return await self._sites.find_one({"custom_domain": domain.lower()})

    async def slug_available(self, slug: str, exclude_site_id: Optional[str] = None) -> bool:
        query: dict[str, Any] = {"slug": slug.lower()}
        if exclude_site_id:
            query["site_id"] = {"$ne": exclude_site_id}
        return await self._sites.count_documents(query, limit=1) == 0

    async def domain_available(self, domain: str, exclude_site_id: Optional[str] = None) -> bool:
        query: dict[str, Any] = {"custom_domain": domain.lower()}
        if exclude_site_id:
            query["site_id"] = {"$ne": exclude_site_id}
        return await self._sites.count_documents(query, limit=1) == 0

    async def update_site(self, site_id: str, fields: dict[str, Any]) -> None:
        fields = dict(fields)
        fields["updated_at"] = utcnow()
        await self._sites.update_one({"site_id": site_id}, {"$set": fields})

    async def inc_views(self, site_id: str) -> None:
        await self._sites.update_one({"site_id": site_id}, {"$inc": {"views_count": 1}})

    async def list_sites_by_owner(self, owner_id: int, skip: int = 0, limit: int = 6) -> list[dict]:
        cursor = (
            self._sites.find({"owner_id": owner_id})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(limit)

    async def count_sites_by_owner(self, owner_id: int) -> int:
        return await self._sites.count_documents({"owner_id": owner_id})

    async def list_all_sites(self, skip: int = 0, limit: int = 8) -> list[dict]:
        cursor = self._sites.find({}).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return await cursor.to_list(limit)

    async def count_sites(self, query: Optional[dict] = None) -> int:
        return await self._sites.count_documents(query or {})

    async def search_sites(self, query: str, limit: int = 8) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        regex = {"$regex": re.escape(query), "$options": "i"}
        return await self._sites.find(
            {"$or": [{"slug": regex}, {"site_name": regex}, {"site_id": query}]}
        ).limit(limit).to_list(limit)

    async def delete_site(self, site_id: str) -> None:
        await self._sites.delete_one({"site_id": site_id})
        await self._qr.delete_many({"site_id": site_id})

    async def delete_sites_of_owner(self, owner_id: int) -> list[str]:
        ids = [d["site_id"] async for d in self._sites.find({"owner_id": owner_id}, {"site_id": 1})]
        for sid in ids:
            await self.delete_site(sid)
        return ids

    # ------------------------------------------------------------------ #
    # QR codes
    # ------------------------------------------------------------------ #
    async def create_qr(self, qr_id: str, site_id: str, style_type: str) -> None:
        await self._qr.insert_one(
            {"qr_id": qr_id, "site_id": site_id, "style_type": style_type, "created_at": utcnow()}
        )

    async def count_qr(self, site_id: Optional[str] = None) -> int:
        return await self._qr.count_documents({"site_id": site_id} if site_id else {})

    # ------------------------------------------------------------------ #
    # Aggregates
    # ------------------------------------------------------------------ #
    async def total_views(self, owner_id: Optional[int] = None) -> int:
        match = {"$match": {"owner_id": owner_id}} if owner_id is not None else {"$match": {}}
        rows = await self._sites.aggregate(
            [match, {"$group": {"_id": None, "v": {"$sum": "$views_count"}}}]
        ).to_list(1)
        return int(rows[0]["v"]) if rows else 0

    async def total_size(self) -> int:
        rows = await self._sites.aggregate(
            [{"$group": {"_id": None, "s": {"$sum": "$size_bytes"}}}]
        ).to_list(1)
        return int(rows[0]["s"]) if rows else 0


# Shared singleton used across the whole application.
db = Database()
