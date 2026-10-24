
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class ChatMemory:

    def __init__(
        self,
        max_messages: int = 10,
        storage_directory: str = "backend/data/chat_memory",
    ):
        self.max_messages = max_messages
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)

        # session_id -> session data
        self.sessions: Dict[str, Dict] = {}

    def _get_session_path(self, session_id: str) -> Path:
        # Prevent path traversal through a user-supplied session ID.
        if not session_id or not re.fullmatch(
            r"[a-zA-Z0-9_-]{1,200}", session_id
        ):
            raise ValueError("Invalid session ID.")

        return self.storage_directory / f"{session_id}.json"

    def _load_session(self, session_id: str) -> Optional[Dict]:
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return None

        try:
            with open(session_path, "r", encoding="utf-8") as file:
                session = json.load(file)
        except (json.JSONDecodeError, OSError):
            return None

        if not isinstance(session, dict):
            return None

        return session

    def _save_session(self, session_id: str):
        session_path = self._get_session_path(session_id)
        session = self.sessions.get(session_id)

        if session is None:
            return

        with open(session_path, "w", encoding="utf-8") as file:
            json.dump(
                session,
                file,
                ensure_ascii=False,
                indent=2,
            )

    def get_history(
        self,
        session_id: str,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        if session_id not in self.sessions:
            session = self._load_session(session_id)
            if session is None:
                return []
            self.sessions[session_id] = session

        session = self.sessions[session_id]

        if (
            document_id is not None
            and session.get("document_id") != document_id
        ):
            return []

        return session.get("messages", [])

    
    
    def ensure_session(
        self,
        session_id: str,
        document_id: str,
        user_id: str,
    ) -> bool:
        if session_id not in self.sessions:
            session = self._load_session(session_id)

            if session is not None:
                self.sessions[session_id] = session

        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "document_id": document_id,
                "user_id": user_id,
                "messages": [],
            }
            self._save_session(session_id)
            return True

        session = self.sessions[session_id]

        return (
            session.get("user_id") == user_id
            and session.get("document_id") == document_id
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ):
        if role not in {"user", "assistant"}:
            raise ValueError("Role must be 'user' or 'assistant'.")

        if not content or not content.strip():
            return

        if session_id not in self.sessions:
            raise ValueError("Session does not exist.")

        session = self.sessions[session_id]
        session["messages"].append(
            {
                "role": role,
                "content": content.strip(),
            }
        )
        session["messages"] = session["messages"][-self.max_messages:]
        self._save_session(session_id)

    def get_document_id(self, session_id: str) -> Optional[str]:
        if session_id not in self.sessions:
            session = self._load_session(session_id)
            if session is None:
                return None
            self.sessions[session_id] = session

        return self.sessions[session_id].get("document_id")

    def clear_session(self, session_id: str):
        self.sessions.pop(session_id, None)

        session_path = self._get_session_path(session_id)
        if session_path.exists():
            session_path.unlink()

    def session_exists(self, session_id: str) -> bool:
        if session_id in self.sessions:
            return True

        return self._get_session_path(session_id).exists()

    def get_all_sessions(self) -> List[str]:
        return [
            file.stem
            for file in self.storage_directory.glob("*.json")
        ]
