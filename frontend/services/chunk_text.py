def overlap_chunking(text, chunk_size=500, overlap=100):
    """
    Splits text into overlapping chunks.

    Args:
        text (str): Complete document text.
        chunk_size (int): Number of characters in one chunk.
        overlap (int): Number of overlapping characters.

    Returns:
        list: List of text chunks.
    """

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        chunks.append(chunk)

        start += (chunk_size - overlap)

    return chunks

def create_chunks(text, chunk_size=500, overlap=100):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append({
                "text": chunk
            })

        start += chunk_size - overlap

    return chunks


def save_chunks(chunks, filename="chunks.txt"):

    with open(filename, "w", encoding="utf-8") as file:

        for index, chunk in enumerate(chunks, start=1):

            file.write("=" * 60 + "\n")
            file.write(f"Chunk {index}\n")
            file.write("=" * 60 + "\n")
            file.write(chunk)
            file.write("\n\n")


def main():

    try:

        with open("output.txt", "r", encoding="utf-8") as file:

            text = file.read()

        print(f"Characters : {len(text)}")
        print(f"Words      : {len(text.split())}")
        print(f"Lines      : {len(text.splitlines())}")

        chunk_size = 500
        overlap = 100

        chunks = overlap_chunking(text, chunk_size, overlap)

        print(f"\nTotal Chunks : {len(chunks)}\n")

        for index, chunk in enumerate(chunks[:3], start=1):

            print("=" * 60)
            print(f"Chunk {index}")
            print("=" * 60)
            print(chunk)
            print()

        save_chunks(chunks)

        print("Chunks saved successfully in chunks.txt")

    except Exception as e:

        print("Error :", e)


if __name__ == "__main__":
    main()