from services.hybrid_retrieval import HybridRetrievalService


retriever = HybridRetrievalService()

question = input("\nEnter your question: ")

results = retriever.search(question)


# ============================================================
# SEMANTIC SEARCH
# ============================================================

print("\n" + "=" * 60)
print("1. SEMANTIC SEARCH")
print("=" * 60)

for result in results["semantic_results"]:

    print(
        f"ID: {result['id']} | "
        f"Distance: {result['semantic_distance']:.4f} | "
        f"{result['metadata']['source']}"
    )


# ============================================================
# BM25 SEARCH
# ============================================================

print("\n" + "=" * 60)
print("2. BM25 KEYWORD SEARCH")
print("=" * 60)

for result in results["keyword_results"]:

    print(
        f"ID: {result['id']} | "
        f"Score: {result['bm25_score']:.4f} | "
        f"{result['metadata']['source']}"
    )


# ============================================================
# MERGED CANDIDATES
# ============================================================

print("\n" + "=" * 60)
print("3. CANDIDATES FOR RERANKING")
print("=" * 60)

print(
    f"Total unique candidates: "
    f"{len(results['candidates'])}"
)

for result in results["candidates"]:

    print(
        f"ID: {result['id']} | "
        f"{result['metadata']['source']}"
    )