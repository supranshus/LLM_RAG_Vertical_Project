import json


class RerankerService:

    def __init__(self, gemini_service):

        self.gemini = gemini_service

    def rerank(self, question, candidates, top_k=3):

        # -----------------------------------------
        # Build candidates for the reranker
        # -----------------------------------------

        candidate_text = ""

        for candidate in candidates:

            candidate_text += f"""
--------------------------------
CHUNK ID: {candidate['id']}
SOURCE: {candidate['metadata']['source']}

TEXT:
{candidate['text']}
--------------------------------
"""

        # -----------------------------------------
        # Create reranker prompt
        # -----------------------------------------

        prompt = f"""
You are a document retrieval reranker.

Your job is NOT to answer the user's question.

Your only job is to identify the most relevant
document chunks that would help another LLM
answer the question.

USER QUESTION:
{question}

CANDIDATE DOCUMENT CHUNKS:

{candidate_text}

Select the {top_k} most relevant chunks.

Return ONLY valid JSON in exactly this format:

{{
    "selected_chunks": ["chunk_id_1", "chunk_id_2", "chunk_id_3"]
}}

Rules:

1. Only select chunk IDs that appear above.
2. Select at most {top_k} chunks.
3. Do not answer the question.
4. Rank the chunks from most relevant to least relevant.
5. Return JSON only.
"""

        # -----------------------------------------
        # Ask Gemini
        # -----------------------------------------

        response = self.gemini.generate(prompt)

        # -----------------------------------------
        # Parse JSON response
        # -----------------------------------------

        try:

            result = json.loads(response)

            selected_ids = result["selected_chunks"]

        except Exception as e:

            print("Reranker returned invalid JSON.")
            print("Response:", response)

            return candidates[:top_k]

        # -----------------------------------------
        # Find the actual candidates
        # -----------------------------------------

        candidate_map = {
            str(candidate["id"]): candidate
            for candidate in candidates
        }

        selected_candidates = []

        for chunk_id in selected_ids:

            chunk_id = str(chunk_id)

            if chunk_id in candidate_map:

                selected_candidates.append(
                    candidate_map[chunk_id]
                )

        return selected_candidates[:top_k]