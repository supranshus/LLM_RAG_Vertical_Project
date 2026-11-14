import fitz


class PDFReader:

    def read_pages(self, file_path):

        document = fitz.open(file_path)

        pages = []

        for page_number in range(document.page_count):

            page = document.load_page(page_number)

            text = page.get_text()

            pages.append({
                "page": page_number + 1,
                "text": text
            })

        document.close()

        return pages