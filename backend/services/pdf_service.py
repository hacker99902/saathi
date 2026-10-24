from pathlib import Path

import pymupdf


def extract_text_from_pdf(file_path: str) -> dict:
    """
    Extract text from a PDF while preserving page boundaries.

    Returns:
        {
            "text": str,
            "pages": [
                {"page_number": int, "text": str}
            ],
            "page_count": int
        }

    Raises:
        FileNotFoundError: The PDF path does not exist.
        ValueError: The path is invalid or the PDF has no extractable text.
    """
    if not isinstance(file_path, (str, Path)) or not str(file_path).strip():
        raise ValueError("A valid PDF file path is required.")

    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if not pdf_path.is_file():
        raise ValueError("The provided path is not a file.")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("The provided file must have a .pdf extension.")

    pages = []

    try:
        with pymupdf.open(str(pdf_path)) as document:
            if document.needs_pass:
                raise ValueError(
                    "The PDF is password-protected and cannot be read "
                    "without its password."
                )

            if len(document) == 0:
                raise ValueError("The PDF contains no pages.")

            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()

                pages.append({
                    "page_number": page_number,
                    "text": text,
                })

    except ValueError:
        raise
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise ValueError(
            "Unable to read the PDF. It may be corrupted, encrypted, "
            "or not a valid PDF file."
        ) from exc

    full_text = "\n\n".join(
        page["text"]
        for page in pages
        if page["text"]
    )

    if not full_text.strip():
        raise ValueError(
            "No extractable text was found in the PDF. "
            "The document may be scanned and require OCR."
        )

    return {
        "text": full_text,
        "pages": pages,
        "page_count": len(pages),
    }


if __name__ == "__main__":
    pdf_file = "backend/introduction_to_machine_learning.pdf"

    try:
        result = extract_text_from_pdf(pdf_file)

        print("PDF extracted successfully!")
        print(f"Number of pages: {result['page_count']}")
        print(f"Total characters: {len(result['text'])}")

        if result["pages"]:
            print("\n--- PAGE 1 ---")
            print(result["pages"][0]["text"][:1000])

    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")