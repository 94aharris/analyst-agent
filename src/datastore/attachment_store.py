import asyncio
import inspect
import json
import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from chatkit.agents import TContext
from chatkit.store import Attachment, AttachmentStore, Store
from chatkit.types import AttachmentCreateParams, FileAttachment, ImageAttachment
from pydantic import AnyUrl, TypeAdapter


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_stored_name(name: str, mime_type: str, fallback: str) -> str:
    candidate = Path(name).name.strip()
    if candidate and candidate != ".":
        return candidate
    extension = mimetypes.guess_extension(mime_type) or ""
    return f"{fallback}{extension}"


def _is_image_mime(mime_type: str) -> bool:
    return mime_type.lower().startswith("image/")


_ANY_URL_ADAPTER = TypeAdapter(AnyUrl)


class RawAttachmentStore(AttachmentStore[TContext]):
    """Simple filesystem-backed attachment store."""

    def __init__(
        self,
        root_dir: str | Path = Path("data/attachments"),
        *,
        public_base_url: str | None = None,
        metadata_store: Store[TContext] | None = None,
    ) -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self._metadata_store = metadata_store

    async def create_attachment(
        self, input: AttachmentCreateParams, context: TContext
    ) -> Attachment:
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        payload = await self._extract_file_bytes(context)
        stored_name = _derive_stored_name(input.name, input.mime_type, attachment_id)

        attachment_dir = self._attachment_dir(attachment_id)
        attachment_dir.mkdir(parents=True, exist_ok=True)

        blob_path = attachment_dir / stored_name
        await asyncio.to_thread(self._write_bytes, blob_path, payload)

        metadata = {
            "id": attachment_id,
            "name": input.name,
            "mime_type": input.mime_type,
            "size": len(payload),
            "stored_name": stored_name,
            "created_at": _utc_now_iso(),
        }
        await asyncio.to_thread(
            self._write_json, attachment_dir / "metadata.json", metadata
        )

        base_kwargs = {
            "id": attachment_id,
            "name": input.name,
            "mime_type": input.mime_type,
            "size": len(payload),
            "upload_url": None,
        }

        if _is_image_mime(input.mime_type):
            preview_url = _ANY_URL_ADAPTER.validate_python(
                self._build_preview_url(attachment_id, stored_name)
            )
            attachment: Attachment = ImageAttachment(
                preview_url=preview_url, **base_kwargs
            )
        else:
            attachment = FileAttachment(**base_kwargs)

        await self._maybe_save_metadata(attachment, context)
        return attachment

    async def delete_attachment(self, attachment_id: str, context: TContext) -> None:
        attachment_dir = self._attachment_dir(attachment_id)
        if not attachment_dir.exists():
            raise KeyError(f"Attachment {attachment_id!r} was not found")

        await asyncio.to_thread(shutil.rmtree, attachment_dir)
        await self._maybe_delete_metadata(attachment_id, context)

    async def get_local_path(self, attachment_id: str, context: TContext) -> Path:
        metadata = await self._load_metadata(attachment_id)
        stored_name = metadata.get("stored_name")
        if not stored_name:
            raise KeyError(
                f"Attachment {attachment_id!r} metadata missing stored file reference"
            )
        return (self._attachment_dir(attachment_id) / stored_name).resolve()

    async def get_metadata(
        self, attachment_id: str, context: TContext
    ) -> dict[str, Any]:
        return await self._load_metadata(attachment_id)

    # ------------------------------------------------------------------
    # Internal helpers
    def _attachment_dir(self, attachment_id: str) -> Path:
        return self._root / attachment_id

    def _build_preview_url(self, attachment_id: str, filename: str) -> str:
        if self._public_base_url:
            return f"{self._public_base_url}/{attachment_id}/{filename}"
        return (self._attachment_dir(attachment_id) / filename).resolve().as_uri()

    async def _extract_file_bytes(self, context: TContext) -> bytes:
        candidate = self._locate_payload(context)
        if candidate is None:
            raise ValueError(
                "RawAttachmentStore requires file bytes in the request context "
                "(via 'file_bytes' or 'file')."
            )

        if isinstance(candidate, (bytes, bytearray, memoryview)):
            return bytes(candidate)

        if isinstance(candidate, str):
            path = Path(candidate)
            if not path.exists():
                raise ValueError(
                    "String attachment payloads must reference an existing file path"
                )
            return await asyncio.to_thread(path.read_bytes)

        if isinstance(candidate, Path):
            return await asyncio.to_thread(candidate.read_bytes)

        read_method = getattr(candidate, "read", None)
        if callable(read_method):
            if inspect.iscoroutinefunction(read_method):
                data = await read_method()
            else:
                data = await asyncio.to_thread(read_method)

            if isinstance(data, (bytes, bytearray, memoryview)):
                return bytes(data)
            if isinstance(data, str):
                return data.encode("utf-8")
            raise TypeError(
                "Attachment source returned unsupported data type from read()"
            )

        nested = getattr(candidate, "file", None)
        if nested is not None and nested is not candidate:
            return await self._extract_file_bytes({"file": nested})  # type: ignore[arg-type]

        raise TypeError(
            "Unsupported attachment payload; provide bytes or a file-like object"
        )

    def _locate_payload(self, context: TContext) -> Any:
        if context is None:
            return None

        candidates: list[Any] = []
        if isinstance(context, Mapping):
            for key in ("file_bytes", "file", "attachment"):
                if key in context and context[key] is not None:
                    candidates.append(context[key])

        for attr in ("file_bytes", "file", "attachment"):
            if hasattr(context, attr):
                value = getattr(context, attr)
                if value is not None:
                    candidates.append(value)

        return next(iter(candidates), None)

    @staticmethod
    def _write_bytes(path: Path, payload: bytes) -> None:
        with path.open("wb") as destination:
            destination.write(payload)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    async def _load_metadata(self, attachment_id: str) -> dict[str, Any]:
        metadata_path = self._attachment_dir(attachment_id) / "metadata.json"
        if not metadata_path.exists():
            raise KeyError(f"Attachment {attachment_id!r} metadata was not found")
        return await asyncio.to_thread(self._read_json, metadata_path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    async def _maybe_save_metadata(
        self, attachment: Attachment, context: TContext
    ) -> None:
        if self._metadata_store is not None:
            await self._metadata_store.save_attachment(attachment, context)

    async def _maybe_delete_metadata(
        self, attachment_id: str, context: TContext
    ) -> None:
        if self._metadata_store is not None:
            await self._metadata_store.delete_attachment(attachment_id, context)
