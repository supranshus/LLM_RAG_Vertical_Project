from sentence_transformers import SentenceTransformer


class EmbeddingService:

    def __init__(self):

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def generate_embeddings(self, chunks):

        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        embeddings = self.model.encode(texts)

        records = []

        for index, (chunk, embedding) in enumerate(
            zip(chunks, embeddings),
            start=1
        ):

            records.append({
                "id": index,
                "text": chunk["text"],
                "embedding": embedding.tolist(),
                "metadata": {
                    "source": chunk["source"],
                    "chunk_id": index
                }
            })

        return records