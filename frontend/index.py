from services.chunk_text import create_chunks
from services.embedding_service import EmbeddingService
from services.chroma_service import ChromaService


DOCUMENTS = [
    "data/python.md",
    "data/machine_learning.md",
    "data/cloud_computing.md"
]


# -----------------------------
# 1. Read all Markdown files
# -----------------------------

documents = []

for file_path in DOCUMENTS:

    with open(file_path, "r", encoding="utf-8") as file:

        text = file.read()

    documents.append({
        "source": file_path,
        "text": text
    })

    print(f"Loaded: {file_path}")


# -----------------------------
# 2. Create chunks
# -----------------------------

chunks = []

for document in documents:

    document_chunks = create_chunks(
        document["text"]
    )

    for chunk in document_chunks:

        chunk["source"] = document["source"]

    chunks.extend(document_chunks)


print(f"\nTotal Chunks: {len(chunks)}")


# -----------------------------
# 3. Generate embeddings
# -----------------------------

embedding_service = EmbeddingService()

records = embedding_service.generate_embeddings(chunks)

print(f"Generated {len(records)} embeddings")


# -----------------------------
# 4. Store in ChromaDB
# -----------------------------

chroma = ChromaService()

# Remove previous documents
chroma.reset_collection()

# Add new documents
chroma.add_documents(records)

print("\nDocuments indexed successfully!")