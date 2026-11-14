from sentence_transformers import SentenceTransformer

from services.chroma_service import ChromaService


class RetrievalService:

    def __init__(self):

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.chroma = ChromaService()

    def search(self, question, top_k=5):

        question_embedding = self.model.encode(question)

        results = self.chroma.query(
            question_embedding,
            top_k
        )

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        ids = results["ids"][0]

        output = []

        for document, metadata, distance, document_id in zip(
            documents,
            metadatas,
            distances,
            ids
        ):

            output.append({
                "id": document_id,
                "text": document,
                "metadata": metadata,
                "semantic_distance": float(distance)
            })

        return output