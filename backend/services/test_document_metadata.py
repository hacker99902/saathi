from backend.services.document_metadata import (
    DocumentMetadataStore
)


store = DocumentMetadataStore()


document_id = "test-document-001"


metadata = {
    "document_id": document_id,
    "filename": "machine_learning.pdf",
    "page_count": 3,
    "chunk_count": 14,
    "vector_count": 14
}


print("================================")
print("DOCUMENT METADATA TEST")
print("================================")


# Save
store.save(metadata)

print("\nMetadata saved.")


# Load
loaded = store.get(document_id)

print("\nLoaded metadata:")

print(loaded)


# Check existence
print(
    "\nDocument exists:",
    store.exists(document_id)
)


# Get all documents
documents = store.get_all()

print("\nAll documents:")

for document in documents:
    print(document)


print("\nMetadata test successful!")