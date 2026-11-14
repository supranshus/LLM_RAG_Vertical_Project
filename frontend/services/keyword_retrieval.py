from rank_bm25 import BM25Okapi


class KeywordRetrievalService:

    def __init__(self, records):

        self.records = records

        # Extract text from every chunk
        documents = [
            record["text"]
            for record in records
        ]

        # Tokenize every document
        tokenized_documents = [
            self.tokenize(document)
            for document in documents
        ]

        # Create BM25 index
        self.bm25 = BM25Okapi(tokenized_documents)

    def tokenize(self, text):

        return text.lower().split()

    def search(self, question, top_k=5):

        # Tokenize user question
        tokenized_question = self.tokenize(question)

        # Calculate BM25 scores
        scores = self.bm25.get_scores(tokenized_question)

        # Get indices of highest scoring documents
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True
        )

        results = []

        for index in ranked_indices[:top_k]:

            record = self.records[index]

            results.append({
                "id": record["id"],
                "text": record["text"],
                "metadata": record["metadata"],
                "bm25_score": float(scores[index])
            })

        return results