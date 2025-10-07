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
        Respond to all requests with 'It's alive' for now.
        """
        # Import necessary types for creating response
        from datetime import datetime
        from chatkit.types import (
            ThreadItemAddedEvent,
            AssistantMessageItem,
            AssistantMessageContent,
        )

        # Create assistant message with "It's alive" response
        message_item = AssistantMessageItem(
            id=f"msg_{datetime.now().timestamp()}",
            thread_id=thread.id,
            created_at=datetime.now(),
            type="assistant_message",
            content=[
                AssistantMessageContent(
                    type="output_text", text="It's alive", annotations=[]
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
