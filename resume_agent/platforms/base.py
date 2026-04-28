from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger
from playwright.async_api import BrowserContext

from resume_agent.core.config import settings
from resume_agent.core.models import Job, ApplicationResult


class BasePlatform(ABC):

    name: str 


    def _session_path(self) -> Path:
        sessions_dir = Path(settings.SESSIONS_DIR)
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir / f"{self.name}_session.json"

    def _session_exists(self) -> bool:
        return self._session_path().exists()

    async def _load_session(self, context: BrowserContext) -> None:
        session_path = self._session_path()
        if not session_path.exists():
            raise FileNotFoundError(f"No saved session for {self.name}. Run save_session first.")

        with open(session_path, "r") as f:
            storage_state = json.load(f)

        cookies = storage_state if isinstance(storage_state, list) else storage_state.get("cookies", [])
        
        # Normalize Chrome extension cookies for Playwright
        normalized = []
        for c in cookies:
            nc = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
            }
            if "expirationDate" in c:
                nc["expires"] = c["expirationDate"]
            elif "expires" in c:
                nc["expires"] = c["expires"]
                
            same_site = c.get("sameSite", "Lax").capitalize()
            if same_site not in ["Strict", "Lax", "None"]:
                same_site = "None" if nc["secure"] else "Lax"
            nc["sameSite"] = same_site
            
            normalized.append(nc)

        await context.add_cookies(normalized)
        logger.info(f"[{self.name}] Loaded saved session from {session_path}")

    async def _save_session(self, context: BrowserContext) -> None:
        session_path = self._session_path()
        storage_state = await context.storage_state()

        with open(session_path, "w") as f:
            json.dump(storage_state, f, indent=2)

        logger.success(f"[{self.name}] Session saved to {session_path}")

    def _delete_session(self) -> None:
        session_path = self._session_path()
        if session_path.exists():
            session_path.unlink()
            logger.info(f"[{self.name}] Session deleted — will re-login next run")


    @abstractmethod
    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        ...

    @abstractmethod
    async def apply(self, job: Job, resume_path: str | None = None) -> ApplicationResult:
        ...

    def __repr__(self) -> str:
        session_status = "session saved" if self._session_exists() else "no session"
        return f"<Platform: {self.name} ({session_status})>"
