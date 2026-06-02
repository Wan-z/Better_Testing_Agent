"""Local filesystem storage — writes to web/data/sessions/{session_id}/."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from web.backend.config import DATA_DIR, SESSION_TTL_DAYS


class LocalStorage:
    def __init__(self, base_dir: Path = DATA_DIR) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str, filename: str) -> Path:
        return self._base / session_id / filename

    def write(self, session_id: str, filename: str, data: bytes) -> None:
        session_dir = self._base / session_id
        session_dir.mkdir(exist_ok=True)
        self._path(session_id, filename).write_bytes(data)

    def read(self, session_id: str, filename: str) -> bytes:
        return self._path(session_id, filename).read_bytes()

    def exists(self, session_id: str, filename: str) -> bool:
        return self._path(session_id, filename).exists()

    def list_sessions(self) -> list[str]:
        return [d.name for d in self._base.iterdir() if d.is_dir()]

    def delete_session(self, session_id: str) -> None:
        shutil.rmtree(self._base / session_id, ignore_errors=True)

    # ── Convenience helpers ───────────────────────────────────────────

    def write_json(self, session_id: str, filename: str, obj: object) -> None:
        self.write(session_id, filename, json.dumps(obj, default=str).encode())

    def read_json(self, session_id: str, filename: str) -> object:
        return json.loads(self.read(session_id, filename))

    def init_session(self, session_id: str) -> None:
        """Write initial metadata.json for a new session."""
        now = datetime.now(timezone.utc)
        self.write_json(session_id, "metadata.json", {
            "session_id": session_id,
            "status": "CREATED",
            "created_at": now.isoformat(),
            "expires_at": now.replace(day=now.day + SESSION_TTL_DAYS).isoformat(),
            "dialogue_turn": 0,
        })

    def get_metadata(self, session_id: str) -> dict:  # type: ignore[type-arg]
        return self.read_json(session_id, "metadata.json")  # type: ignore[return-value]

    def set_status(self, session_id: str, status: str) -> None:
        meta = self.get_metadata(session_id)
        meta["status"] = status
        self.write_json(session_id, "metadata.json", meta)

    def cleanup_expired(self) -> int:
        """Delete sessions past their expiry. Returns count deleted."""
        deleted = 0
        now = datetime.now(timezone.utc)
        for sid in self.list_sessions():
            try:
                meta = self.get_metadata(sid)
                expires = datetime.fromisoformat(meta["expires_at"])
                if now > expires:
                    self.delete_session(sid)
                    deleted += 1
            except Exception:
                pass
        return deleted
