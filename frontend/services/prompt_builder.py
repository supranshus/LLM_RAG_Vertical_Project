class PromptBuilder:

    @staticmethod
    def build(question, results, conversation_history):

        # ---------------------------------
        # Build conversation history
        # ---------------------------------

        history_text = ""

        for message in conversation_history:

            history_text += (
                f"{message['role'].upper()}: "
                f"{message['content']}\n\n"
            )

        # ---------------------------------
        # Build retrieved context
        # ---------------------------------

        context_parts = []

        for result in results:

            metadata = result["metadata"]

            source = metadata["source"]
            chunk_id = metadata["chunk_id"]

            context_parts.append(
                f"""
[Source: {source}, Chunk: {chunk_id}]

{result["text"]}
"""
            )

        context = "\n\n".join(context_parts)

        # ---------------------------------
        # Build final prompt
        # ---------------------------------

        prompt = f"""
You are a helpful AI assistant.

Answer the user's question using the provided document context.

You may use the conversation history to understand
references such as "that", "it", "they", "this", etc.

Do NOT treat conversation history as factual document evidence.
Use the retrieved document context as the source of truth.

If the answer cannot be found in the document context,
say:

"I couldn't find that information in the document."

Always mention the source document when
document information is used.

==============================
CONVERSATION HISTORY
==============================

{history_text}

==============================
DOCUMENT CONTEXT
==============================

{context}

==============================
CURRENT QUESTION
==============================

{question}

==============================
ANSWER
==============================
"""

        return prompt