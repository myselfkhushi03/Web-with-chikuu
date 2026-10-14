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
        assert self.db is not None
        await self.db.users.create_index("telegram_id", unique=True)
        await self.db.users.create_index("username")
        await self.db.sites.create_index("site_id", unique=True)
        await self.db.sites.create_index("slug", unique=True)
        await self.db.sites.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
        # Unique custom domains, but many sites may have an empty one.
        await self.db.sites.create_index(
            "custom_domain",
            unique=True,
            partialFilterExpression={"custom_domain": {"$gt": ""}},
        )
        await self.db.qr_codes.create_index("qr_id", unique=True)
        await self.db.qr_codes.create_index("site_id")

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