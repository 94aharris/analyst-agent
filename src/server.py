import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Tuple

from chatkit.server import ChatKitServer
from chatkit.store import AttachmentStore, Store
from chatkit.types import (
    Attachment,
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadItemAddedEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)


class MyChatKitServer(ChatKitServer):
    def __init__(
        self, data_store: Store, attachment_store: AttachmentStore | None = None
    ):
        super().__init__(data_store, attachment_store)
        # Store Claude session IDs per thread
        self.claude_sessions: dict[str, str] = {}

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Invoke Claude headless mode and return a single message."""
        if not input_user_message:
            return

        user_text = self._extract_user_text(input_user_message)

        attachment_blocks: list[str] = []
        attachment_env_payload: list[dict[str, Any]] = []
        attachments = getattr(input_user_message, "attachments", None) or []
        for attachment in attachments:
            block, env_entry = await self._build_attachment_context(attachment, context)
            if block:
                attachment_blocks.append(block)
            if env_entry:
                attachment_env_payload.append(env_entry)

        if attachment_blocks:
            user_text = f"{user_text}\n\n[Attachments]\n" + "\n".join(attachment_blocks)

        session_id = self.claude_sessions.get(thread.id)
        process_env = (
            self._build_process_env(attachment_env_payload)
            if attachment_env_payload
            else None
        )

        args = ["claude", "-p", user_text, "--output-format", "json"]
        if session_id:
            args.extend(["--resume", session_id])

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=process_env,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            response_text = f"Error invoking Claude: {stderr.decode().strip()}"
        else:
            try:
                payload = json.loads(stdout.decode())
            except json.JSONDecodeError:
                payload = {}

            response_text = payload.get("result") or stdout.decode().strip()
            new_session = payload.get("session_id")
            if new_session:
                self.claude_sessions[thread.id] = new_session

        message_item = AssistantMessageItem(
            id=f"msg_{datetime.now().timestamp()}",
            thread_id=thread.id,
            created_at=datetime.now(),
            type="assistant_message",
            content=[
                AssistantMessageContent(
                    type="output_text",
                    text=response_text,
                    annotations=[],
                )
            ],
        )
        yield ThreadItemAddedEvent(type="thread.item.added", item=message_item)

    def _extract_user_text(self, message: UserMessageItem) -> str:
        text_parts: list[str] = []
        if message.content:
            for content_item in message.content:
                item_text = getattr(content_item, "text", None)
                if item_text:
                    text_parts.append(item_text)
        return "".join(text_parts)

    async def _build_attachment_context(
        self, attachment: Attachment, request_context: Any
    ) -> Tuple[str | None, dict[str, Any] | None]:
        store = getattr(self, "attachment_store", None)
        if store is None or not hasattr(store, "get_local_path"):
            return None, None

        try:
            path = Path(await store.get_local_path(attachment.id, request_context))
        except Exception as exc:  # pragma: no cover - best effort logging
            return (
                f"- Attachment {attachment.name or attachment.id}: unavailable ({exc})",
                None,
            )

        mime_type = getattr(attachment, "mime_type", None)
        details = [
            f"- {attachment.name or attachment.id} — {mime_type or 'unknown'}",
            f"  {path}",
        ]
        env_entry: dict[str, Any] = {
            "id": attachment.id,
            "name": attachment.name,
            "mime_type": mime_type,
            "path": str(path),
        }

        return "\n".join(details), env_entry

    @staticmethod
    def _build_process_env(attachments: list[dict[str, Any]]) -> dict[str, str]:
        env = os.environ.copy()
        env["CHATKIT_ATTACHMENTS"] = json.dumps(attachments)
        return env
