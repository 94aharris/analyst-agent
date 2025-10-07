from typing import Any, AsyncIterator
from chatkit.server import ChatKitServer
from chatkit.store import Store, AttachmentStore
from chatkit.agents import AgentContext
from chatkit.types import ThreadMetadata, UserMessageItem, ThreadStreamEvent


class MyChatKitServer(ChatKitServer):
    def __init__(
        self, data_store: Store, attachment_store: AttachmentStore | None = None
    ):
        super().__init__(data_store, attachment_store)

    # Commented out for now - will be used later
    # assistant_agent = Agent[AgentContext](
    #     model="gpt-4.1", name="Assistant", instructions="You are a helpful assistant"
    # )

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: Any,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """
        Invoke Claude headless mode and stream back the response.
        """
        import asyncio
        from datetime import datetime
        from chatkit.types import (
            ThreadItemAddedEvent,
            AssistantMessageItem,
            AssistantMessageContent,
        )

        # Extract the user's message text
        if not input_user_message:
            return

        user_text = ""
        if input_user_message.content:
            for content_item in input_user_message.content:
                if hasattr(content_item, "text"):
                    user_text += content_item.text

        # Invoke Claude headless mode
        process = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            user_text,
            "--output-format",
            "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Read the output
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            response_text = f"Error invoking Claude: {stderr.decode()}"
        else:
            response_text = stdout.decode()

        # Create assistant message with Claude's response
        message_item = AssistantMessageItem(
            id=f"msg_{datetime.now().timestamp()}",
            thread_id=thread.id,
            created_at=datetime.now(),
            type="assistant_message",
            content=[
                AssistantMessageContent(
                    type="output_text", text=response_text, annotations=[]
                )
            ],
        )

        # Yield the event
        yield ThreadItemAddedEvent(type="thread.item.added", item=message_item)

        # Original implementation - commented out for now
        # agent_context = AgentContext(
        #     thread=thread,
        #     store=self.store,
        #     request_context=context,
        # )
        # result = Runner.run_streamed(
        #     self.assistant_agent,
        #     await simple_to_agent_input(input_user_message) if input_user_message else [],
        #     context=agent_context,
        # )
        # async for event in stream_agent_response(
        #     agent_context,
        #     result,
        # ):
        #     yield event
