from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service, get_current_user, get_session_closer
from app.api.schemas.chat import ConversationCreate, ConversationRead, MessageCreate, MessageRead
from app.core.security import CurrentUser
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/v1/conversations", tags=["chat"])


@router.post("", status_code=201, response_model=ConversationRead)
def create_conversation(
    body: ConversationCreate,
    user: CurrentUser = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
) -> ConversationRead:
    conversation = chat.create_conversation(user, body.title, body.knowledge_scope)
    return ConversationRead.model_validate(conversation)


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    user: CurrentUser = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
) -> list[ConversationRead]:
    return [ConversationRead.model_validate(c) for c in chat.list_conversations(user)]


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: int,
    user: CurrentUser = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
) -> list[MessageRead]:
    return [MessageRead.model_validate(m) for m in chat.get_messages(user, conversation_id)]


@router.post("/{conversation_id}/messages", response_model=MessageRead)
def send_message(
    conversation_id: int,
    body: MessageCreate,
    user: CurrentUser = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
) -> MessageRead:
    return MessageRead.model_validate(chat.send_message(user, conversation_id, body.content))


@router.post("/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: int,
    body: MessageCreate,
    user: CurrentUser = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
    release_session: Callable[[], None] = Depends(get_session_closer),
) -> StreamingResponse:
    chunks = chat.start_stream(user, conversation_id, body.content)

    def body_stream() -> Iterator[str]:
        try:
            yield from chunks
        finally:
            # The reply is saved at the end of the stream; release the session afterwards
            # whether or not FastAPI has already closed request dependencies.
            release_session()

    return StreamingResponse(body_stream(), media_type="text/plain; charset=utf-8")
