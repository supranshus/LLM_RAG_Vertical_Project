import chromadb


class ChromaService:

    def __init__(self):

        self.client = chromadb.PersistentClient(
            path="chroma_db"
        )

        self.collection = self.client.get_or_create_collection(
            name="company_documents"
        )

    def add_documents(self, records):

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for record in records:

            ids.append(str(record["id"]))

            documents.append(record["text"])

            embeddings.append(record["embedding"])

            metadatas.append(record["metadata"])

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def reset_collection(self):

        self.client.delete_collection("company_documents")

        self.collection = self.client.get_or_create_collection(
            name="company_documents"
        )

    def query(self, question_embedding, top_k=5):

        results = self.collection.query(
            query_embeddings=[question_embedding.tolist()],
            n_results=top_k
        )

        return results

    def get_all_documents(self):

        results = self.collection.get(
            include=["documents", "metadatas", "embeddings"]
        )

        records = []

        for index in range(len(results["ids"])):

            records.append({
                "id": results["ids"][index],
                "text": results["documents"][index],
                "metadata": results["metadatas"][index],
                "embedding": results["embeddings"][index]
            })

        return records