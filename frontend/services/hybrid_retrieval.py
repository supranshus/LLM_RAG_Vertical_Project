from services.chroma_service import ChromaService
from services.retrieval import RetrievalService
from services.keyword_retrieval import KeywordRetrievalService


class HybridRetrievalService:

    def __init__(self):

        self.semantic_retriever = RetrievalService()

        self.chroma = ChromaService()

        # Get all chunks from ChromaDB
        records = self.chroma.get_all_documents()

        # Create BM25 index
        self.keyword_retriever = KeywordRetrievalService(records)

    def search(self, question, top_k=5):

        # -----------------------------------
        # 1. Semantic Search
        # -----------------------------------

        semantic_results = self.semantic_retriever.search(
            question,
            top_k
        )

        # -----------------------------------
        # 2. Keyword Search
        # -----------------------------------

        keyword_results = self.keyword_retriever.search(
            question,
            top_k
        )

        # -----------------------------------
        # 3. Merge results
        # -----------------------------------

        merged = {}

        for result in semantic_results:

            document_id = result["id"]

            merged[document_id] = result

        for result in keyword_results:

            document_id = result["id"]

            if document_id in merged:

                merged[document_id]["bm25_score"] = result["bm25_score"]

            else:

                merged[document_id] = result

        # -----------------------------------
        # 4. Convert dictionary to list
        # -----------------------------------

        candidates = list(merged.values())

        return {
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
            "candidates": candidates
        }