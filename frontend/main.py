from services.retrieval import RetrievalService
from services.prompt_builder import PromptBuilder
from services.gemini_service import GeminiService

retriever = RetrievalService()
gemini = GeminiService()
conversation_history = []

print("=" * 60)
print("Enterprise RAG Assistant")
print("=" * 60)

while True:

    question = input("\nYou: ")

    if question.lower() == "exit":
        break

    results = retriever.search(question)

    print("\nRetrieved Sources:")

    for result in results:

        print(
            f"Source: {result['metadata']['source']} | "
            f"Chunk: {result['metadata']['chunk_id']} | "
            f"Distance: {result['distance']:.4f}"
        )

    prompt = PromptBuilder.build(
        question,
        results,
        conversation_history
    )

    answer = gemini.generate(prompt)

    print("\nAssistant:\n")
    print(answer)

    conversation_history.append({
        "role": "user",
        "content": question
    })

    conversation_history.append({
        "role": "assistant",
        "content": answer
    })