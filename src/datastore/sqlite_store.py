import asyncio
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, TypeVar

from chatkit.agents import TContext
from chatkit.store import Attachment, Page, Store, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter

from src.config import get_settings


T = TypeVar("T")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_order(order: str) -> str:
    order = order.lower()
    return "desc" if order not in {"asc", "desc"} else order


@dataclass(slots=True)
class _PaginationState:
    has_more: bool
    next_after: str | None


class SqliteStore(Store[TContext]):
    """SQLite-backed implementation of :class:`chatkit.store.Store`.

    Threads, thread items, and attachments are persisted as JSON blobs to
    preserve forward compatibility with evolving ChatKit schemas.
    """

    _THREAD_ADAPTER = TypeAdapter(ThreadMetadata)
    _THREAD_ITEM_ADAPTER = TypeAdapter(ThreadItem)
    _ATTACHMENT_ADAPTER = TypeAdapter(Attachment)

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = get_settings().db_path
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Public API - threads
    async def load_thread(self, thread_id: str, context: TContext) -> ThreadMetadata:
        row = await self._query_one(
            "SELECT data FROM threads WHERE id = ?", (thread_id,)
        )
        if row is None:
            raise KeyError(f"Thread {thread_id!r} was not found")
        return self._THREAD_ADAPTER.validate_json(row["data"])

    async def save_thread(self, thread: ThreadMetadata, context: TContext) -> None:
        thread_json = thread.model_dump_json()
        thread_created = getattr(thread, "created_at", None)
        if hasattr(thread_created, "isoformat"):
            created_at: str = thread_created.isoformat()  # type: ignore[assignment]
        elif isinstance(thread_created, str):
            created_at = thread_created
        else:
            created_at = _utc_now_iso()
        updated_at = _utc_now_iso()

        await self._execute(
            (
                "INSERT INTO threads (id, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data, "
                "updated_at = excluded.updated_at"
            ),
            (
                thread.id,
                thread_json,
                created_at,
                updated_at,
            ),
        )

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: TContext,
    ) -> Page[ThreadMetadata]:
        order = _safe_order(order)

        def worker(
            conn: sqlite3.Connection,
        ) -> tuple[list[ThreadMetadata], _PaginationState]:
            params: list[str | int | float | None] = []
            where_clause = ""
            if after:
                row = conn.execute(
                    "SELECT updated_at, id FROM threads WHERE id = ?", (after,)
                ).fetchone()
                if row is not None:
                    updated_at = row["updated_at"]
                    comparator = "<" if order == "desc" else ">"
                    where_clause = (
                        "WHERE (updated_at {cmp} ?) OR (updated_at = ? AND id {cmp} ?)"
                    ).format(cmp=comparator)
                    params.extend([updated_at, updated_at, after])
            params.append(limit + 1)
            base_query = "SELECT id, data FROM threads"
            if where_clause:
                base_query = f"{base_query} {where_clause}"
            query = f"{base_query} ORDER BY updated_at {order.upper()}, id {order.upper()} LIMIT ?"
            rows = conn.execute(query, tuple(params)).fetchall()
            has_more = len(rows) > limit
            data_rows = rows[:limit]
            threads = [
                self._THREAD_ADAPTER.validate_json(row["data"]) for row in data_rows
            ]
            next_after = data_rows[-1]["id"] if has_more or threads else None
            return threads, _PaginationState(has_more=has_more, next_after=next_after)

        threads, state = await self._with_connection(worker)
        return Page(data=threads, has_more=state.has_more, after=state.next_after)

    async def delete_thread(self, thread_id: str, context: TContext) -> None:
        changes = await self._execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        if changes == 0:
            raise KeyError(f"Thread {thread_id!r} was not found")

    # ------------------------------------------------------------------
    # Public API - thread items
    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: TContext,
    ) -> Page[ThreadItem]:
        order = _safe_order(order)

        def worker(
            conn: sqlite3.Connection,
        ) -> tuple[list[ThreadItem], _PaginationState]:
            params: list[str | int | float | None] = [thread_id]
            after_clause = ""
            comparator = "<" if order == "desc" else ">"
            if after:
                row = conn.execute(
                    "SELECT position FROM thread_items WHERE thread_id = ? AND id = ?",
                    (thread_id, after),
                ).fetchone()
                if row is not None:
                    after_clause = f"AND position {comparator} ?"
                    params.append(row["position"])
            params.append(limit + 1)
            query = (
                "SELECT id, data FROM thread_items WHERE thread_id = ? "
                f"{after_clause} ORDER BY position {order.upper()}, id {order.upper()} LIMIT ?"
            )
            rows = conn.execute(query, tuple(params)).fetchall()
            has_more = len(rows) > limit
            data_rows = rows[:limit]
            items = [
                self._THREAD_ITEM_ADAPTER.validate_json(row["data"])
                for row in data_rows
            ]
            next_after = data_rows[-1]["id"] if has_more or items else None
            return items, _PaginationState(has_more=has_more, next_after=next_after)

        items, state = await self._with_connection(worker)
        return Page(data=items, has_more=state.has_more, after=state.next_after)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: TContext
    ) -> None:
        item_json = self._THREAD_ITEM_ADAPTER.dump_json(item).decode("utf-8")
        created_at_val = getattr(item, "created_at", None)
        if hasattr(created_at_val, "isoformat"):
            created_at_str = created_at_val.isoformat()  # type: ignore[assignment]
        elif isinstance(created_at_val, str):
            created_at_str = created_at_val
        else:
            created_at_str = _utc_now_iso()

        item_id = getattr(item, "id", None)
        if not item_id:
            raise ValueError("Thread items must have an 'id' to be added")

        def worker(conn: sqlite3.Connection) -> None:
            position_row = conn.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM thread_items WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            position = position_row[0] if position_row is not None else 0
            conn.execute(
                "INSERT INTO thread_items (id, thread_id, data, created_at, position) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    item_id,
                    thread_id,
                    item_json,
                    created_at_str,
                    position,
                ),
            )
            conn.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (
                    _utc_now_iso(),
                    thread_id,
                ),
            )

        await self._with_connection(worker)

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: TContext
    ) -> None:
        item_json = self._THREAD_ITEM_ADAPTER.dump_json(item).decode("utf-8")
        item_id = getattr(item, "id", None)
        if not item_id:
            raise ValueError("Thread items must have an 'id' to be saved")

        changes = await self._execute(
            "UPDATE thread_items SET data = ? WHERE thread_id = ? AND id = ?",
            (
                item_json,
                thread_id,
                item_id,
            ),
        )
        if changes == 0:
            raise KeyError(
                f"Thread item {item_id!r} in thread {thread_id!r} was not found"
            )

    async def load_item(
        self, thread_id: str, item_id: str, context: TContext
    ) -> ThreadItem:
        row = await self._query_one(
            "SELECT data FROM thread_items WHERE thread_id = ? AND id = ?",
            (
                thread_id,
                item_id,
            ),
        )
        if row is None:
            raise KeyError(
                f"Thread item {item_id!r} in thread {thread_id!r} was not found"
            )
        return self._THREAD_ITEM_ADAPTER.validate_json(row["data"])

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: TContext
    ) -> None:
        changes = await self._execute(
            "DELETE FROM thread_items WHERE thread_id = ? AND id = ?",
            (
                thread_id,
                item_id,
            ),
        )
        if changes == 0:
            raise KeyError(
                f"Thread item {item_id!r} in thread {thread_id!r} was not found"
            )

    # ------------------------------------------------------------------
    # Public API - attachments
    async def save_attachment(self, attachment: Attachment, context: TContext) -> None:  # type: ignore[override]
        attachment_json = self._ATTACHMENT_ADAPTER.dump_json(attachment).decode("utf-8")
        created_at_val = getattr(attachment, "created_at", None)
        if hasattr(created_at_val, "isoformat"):
            created_at = created_at_val.isoformat()  # type: ignore[assignment]
        elif isinstance(created_at_val, str):
            created_at = created_at_val
        else:
            created_at = _utc_now_iso()
        updated_at = _utc_now_iso()

        await self._execute(
            (
                "INSERT INTO attachments (id, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data, "
                "updated_at = excluded.updated_at"
            ),
            (
                attachment.id,
                attachment_json,
                created_at,
                updated_at,
            ),
        )

    async def load_attachment(
        self, attachment_id: str, context: TContext
    ) -> Attachment:  # type: ignore[override]
        row = await self._query_one(
            "SELECT data FROM attachments WHERE id = ?",
            (attachment_id,),
        )
        if row is None:
            raise KeyError(f"Attachment {attachment_id!r} was not found")
        return self._ATTACHMENT_ADAPTER.validate_json(row["data"])

    async def delete_attachment(self, attachment_id: str, context: TContext) -> None:  # type: ignore[override]
        changes = await self._execute(
            "DELETE FROM attachments WHERE id = ?",
            (attachment_id,),
        )
        if changes == 0:
            raise KeyError(f"Attachment {attachment_id!r} was not found")

    # ------------------------------------------------------------------
    # Internal helpers
    def _ensure_schema(self) -> None:
        def worker(conn: sqlite3.Connection) -> None:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS thread_items (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_thread_items_thread_position
                ON thread_items(thread_id, position)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

        self._with_connection_sync(worker)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    async def _execute(self, query: str, params: Sequence[object]) -> int:
        def worker(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount

        return await self._with_connection(worker)

    async def _query_one(
        self, query: str, params: Sequence[object]
    ) -> sqlite3.Row | None:
        def worker(conn: sqlite3.Connection) -> sqlite3.Row | None:
            cursor = conn.execute(query, tuple(params))
            return cursor.fetchone()

        return await self._with_connection(worker)

    async def _with_connection(self, worker: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._with_connection_sync, worker)

    def _with_connection_sync(self, worker: Callable[[sqlite3.Connection], T]) -> T:
        with self._connect() as conn:
            return worker(conn)
