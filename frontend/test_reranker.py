from services.hybrid_retrieval import HybridRetrievalService
from services.gemini_service import GeminiService
from services.reranker import RerankerService


# -----------------------------------------
# Create services
# -----------------------------------------

retriever = HybridRetrievalService()

gemini = GeminiService()

reranker = RerankerService(gemini)


# -----------------------------------------
# Get question
# -----------------------------------------

question = input("\nEnter your question: ")


# -----------------------------------------
# Hybrid retrieval
# -----------------------------------------

results = retriever.search(question)

candidates = results["candidates"]


print("\n" + "=" * 60)
print("RETRIEVED CANDIDATES")
print("=" * 60)

for candidate in candidates:

    print(
        f"ID: {candidate['id']} | "
        f"Source: {candidate['metadata']['source']}"
    )


print(
    f"\nTotal candidates: "
    f"{len(candidates)}"
)


# -----------------------------------------
# Reranking
# -----------------------------------------

selected = reranker.rerank(
    question,
    candidates,
    top_k=3
)


print("\n" + "=" * 60)
print("RERANKER SELECTED TOP 3")
print("=" * 60)


for rank, candidate in enumerate(
    selected,
    start=1
):

    print(
        f"{rank}. "
        f"ID: {candidate['id']} | "
        f"Source: {candidate['metadata']['source']}"
    )