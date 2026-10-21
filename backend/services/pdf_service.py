import pymupdf
from pathlib import Path


def extract_text_from_pdf(file_path: str) -> dict:
    """
    Extract text from a PDF while preserving page boundaries.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Dictionary containing:
        - text: Complete extracted text
        - pages: List of page-wise text
        - page_count: Number of pages
    """

    pdf_path = Path(file_path)

    # Check whether the file exists
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    # Check file extension
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("The provided file is not a PDF.")

    pages = []

    # Open PDF
    document = pymupdf.open(file_path)

    try:
        # Extract text page by page
        for page_number, page in enumerate(document, start=1):

            text = page.get_text("text").strip()

            pages.append({
                "page_number": page_number,
                "text": text
            })

    finally:
        document.close()

    # Combine all pages into one text
    full_text = "\n\n".join(
        page["text"]
        for page in pages
        if page["text"]
    )

    return {
        "text": full_text,
        "pages": pages,
        "page_count": len(pages)
    }


if __name__ == "__main__":

    # Change this to the path of your PDF
    pdf_file = "backend/introduction_to_machine_learning.pdf"

    try:
        result = extract_text_from_pdf(pdf_file)

        print("PDF extracted successfully!")
        print(f"Number of pages: {result['page_count']}")
        print(f"Total characters: {len(result['text'])}")

        print("\n--- PAGE 1 ---")

        if result["pages"]:
            print(result["pages"][0]["text"][:1000])

    except Exception as error:
        print(f"Error: {error}")
