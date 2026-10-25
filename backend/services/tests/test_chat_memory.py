from ..chat_memory import ChatMemory


def main():

    print("\n================================")
    print("PHASE 9G - CHAT MEMORY TEST")
    print("================================")

    memory = ChatMemory(
        max_messages=10
    )

    session_id = "phase-9g-test"

    # ------------------------------------------
    # Clear previous test
    # ------------------------------------------

    memory.clear_session(
        session_id
    )

    # ------------------------------------------
    # Add messages
    # ------------------------------------------

    memory.add_message(
        session_id=session_id,
        role="user",
        content="What is machine learning?"
    )

    memory.add_message(
        session_id=session_id,
        role="assistant",
        content=(
            "Machine learning is a branch "
            "of Artificial Intelligence."
        )
    )

    memory.add_message(
        session_id=session_id,
        role="user",
        content="What are its types?"
    )

    memory.add_message(
        session_id=session_id,
        role="assistant",
        content=(
            "The document describes "
            "different types of machine learning."
        )
    )

    # ------------------------------------------
    # Read history
    # ------------------------------------------

    history = memory.get_history(
        session_id
    )

    print("\nConversation history:")
    print("--------------------------------")

    for message in history:

        print(
            f"{message['role']}: "
            f"{message['content']}"
        )

    # ------------------------------------------
    # Check session
    # ------------------------------------------

    print("\nSession exists:")

    print(
        memory.session_exists(
            session_id
        )
    )

    # ------------------------------------------
    # Show sessions
    # ------------------------------------------

    print("\nAll sessions:")

    print(
        memory.get_all_sessions()
    )

    print("\n================================")
    print("PHASE 9G TEST PASSED")
    print("================================")


if __name__ == "__main__":
    main()