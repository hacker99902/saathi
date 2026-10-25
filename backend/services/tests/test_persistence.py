from ..document_store import DocumentStore


# --------------------------------------------------
# Configuration
# --------------------------------------------------

DOCUMENT_ID = (
    "c62e2ab3-7c81-4d6c-a170-89609794e4b7"
)


# --------------------------------------------------
# Persistence test
# --------------------------------------------------

def test_persistence():

    print("================================")
    print("PERSISTENCE LOAD TEST")
    print("================================")

    print(
        f"Document ID: {DOCUMENT_ID}"
    )


    # ----------------------------------------------
    # Create document store
    # ----------------------------------------------

    store = DocumentStore()


    # ----------------------------------------------
    # Load existing document
    # ----------------------------------------------

    vector_store = store.load_document(
        DOCUMENT_ID
    )


    # ----------------------------------------------
    # Print counts
    # ----------------------------------------------

    print(
        f"Vectors loaded: "
        f"{vector_store.count()}"
    )

    print(
        f"Chunks loaded: "
        f"{len(vector_store.chunks)}"
    )


    # ----------------------------------------------
    # Check whether data exists
    # ----------------------------------------------

    if vector_store.count() == 0:

        print(
            "\nERROR: No vectors were loaded."
        )

        return


    if not vector_store.chunks:

        print(
            "\nERROR: No chunks were loaded."
        )

        return


    # ----------------------------------------------
    # Show first chunk
    # ----------------------------------------------

    print("\nFirst chunk:")
    print("--------------------------------")

    print(
        vector_store.chunks[0]["text"][:500]
    )


    # ----------------------------------------------
    # Final result
    # ----------------------------------------------

    print("\n================================")
    print("PERSISTENCE TEST PASSED")
    print("================================")


# --------------------------------------------------
# Run test
# --------------------------------------------------

if __name__ == "__main__":
    test_persistence()
