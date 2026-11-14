import logging
from collections.abc import Iterator
from typing import Any

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentUser
from app.core.types import KnowledgeScope
from app.db.models import Conversation, Message
from app.llm.base import ChatMessage, LLMProvider
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.services.retrieval_service import RetrievalService, RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "New chat"
TITLE_LENGTH = 60
RAG_INSTRUCTIONS = (
    "Answer using only the numbered document excerpts below. Cite excerpts like [1]. "
    "If the excerpts do not contain the answer, say you don't know based on the available "
    "documents."
)
NO_MATCHES = "No documents matched this question."
INTERRUPTED_NOTICE = "\n\n[Response interrupted. Please try again.]"


class ChatService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        llm: LLMProvider,
        retrieval: RetrievalService,
        system_prompt: str,
        history_limit: int,
    ):
        self.conversations = conversations
        self.messages = messages
        self.llm = llm
        self.retrieval = retrieval
        self.system_prompt = system_prompt
        self.history_limit = history_limit

    def create_conversation(
        self,
        user: CurrentUser,
        title: str | None = None,
        knowledge_scope: KnowledgeScope = "none",
    ) -> Conversation:
        return self.conversations.create(user.id, title or DEFAULT_TITLE, knowledge_scope)

    def list_conversations(self, user: CurrentUser) -> list[Conversation]:
        return self.conversations.list_for_user(user.id)

    def get_messages(self, user: CurrentUser, conversation_id: int) -> list[Message]:
        conversation = self._get_owned(user, conversation_id)
        return self.messages.list_for_conversation(conversation.id)

    def send_message(self, user: CurrentUser, conversation_id: int, content: str) -> Message:
        """Ask the model and return its reply. Nothing is saved unless the model answers."""
        conversation = self._get_owned(user, conversation_id)
        context, sources = self._build_context(user, conversation, content)
        response = self.llm.chat(context)

        self.messages.add(conversation.id, "user", content)
        reply = self.messages.add(
            conversation.id,
            "assistant",
            response.content,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            sources=sources,
        )
        self._after_exchange(conversation, content)
        return reply

    def start_stream(self, user: CurrentUser, conversation_id: int, content: str) -> Iterator[str]:
        """Start a streamed reply.

        Everything that can fail cleanly (ownership, retrieval, the model's first chunk)
        happens before this returns, so those errors become normal HTTP errors.
        """
        conversation = self._get_owned(user, conversation_id)
        context, sources = self._build_context(user, conversation, content)
        stream = self.llm.stream_chat(context)
        first = next(stream, None)

        self.messages.add(conversation.id, "user", content)
        self._after_exchange(conversation, content)
        return self._continue_stream(conversation, first, stream, sources)

    def _continue_stream(
        self,
        conversation: Conversation,
        first: str | None,
        stream: Iterator[str],
        sources: list[dict[str, Any]] | None,
    ) -> Iterator[str]:
        parts: list[str] = []
        try:
            if first is not None:
                parts.append(first)
                yield first
            for chunk in stream:
                parts.append(chunk)
                yield chunk
        except AppError as exc:
            logger.warning("Stream for conversation %s interrupted: %s", conversation.id, exc.code)
            yield INTERRUPTED_NOTICE
            return
        except Exception:
            # Headers are already sent, so an HTTP error is no longer possible; tell the user.
            logger.exception("Stream for conversation %s failed unexpectedly", conversation.id)
            yield INTERRUPTED_NOTICE
            return
        self.messages.add(
            conversation.id,
            "assistant",
            "".join(parts),
            model=self.llm.default_model,
            sources=sources,
        )
        self.conversations.update(conversation)

    def _get_owned(self, user: CurrentUser, conversation_id: int) -> Conversation:
        conversation = self.conversations.get_for_user(conversation_id, user.id)
        if conversation is None:
            raise NotFoundError("Conversation not found")
        return conversation

    def _build_context(
        self, user: CurrentUser, conversation: Conversation, content: str
    ) -> tuple[list[ChatMessage], list[dict[str, Any]] | None]:
        system = self.system_prompt
        sources = None
        if conversation.knowledge_scope != "none":
            chunks = self.retrieval.search(user, conversation.knowledge_scope, content)
            system = f"{system}\n\n{RAG_INSTRUCTIONS}\n\n{_format_excerpts(chunks)}"
            sources = _sources(chunks)

        history = self.messages.list_for_conversation(conversation.id, limit=self.history_limit)
        context = [ChatMessage("system", system)]
        context += [ChatMessage(m.role, m.content) for m in history if m.role != "system"]
        context.append(ChatMessage("user", content))
        return context, sources

    def _after_exchange(self, conversation: Conversation, content: str) -> None:
        title = None
        if conversation.title == DEFAULT_TITLE:
            title = " ".join(content.split())[:TITLE_LENGTH] or DEFAULT_TITLE
        self.conversations.update(conversation, title=title)


def _format_excerpts(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return NO_MATCHES
    excerpts = []
    for number, chunk in enumerate(chunks, start=1):
        where = chunk.filename if chunk.page is None else f"{chunk.filename}, page {chunk.page}"
        excerpts.append(f"[{number}] ({where})\n{chunk.text}")
    return "\n\n".join(excerpts)


def _sources(chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    seen: set[tuple[int, int | None]] = set()
    sources = []
    for chunk in chunks:
        key = (chunk.document_id, chunk.page)
        if key not in seen:
            seen.add(key)
            sources.append(
                {"document_id": chunk.document_id, "filename": chunk.filename, "page": chunk.page}
            )
    return sources
