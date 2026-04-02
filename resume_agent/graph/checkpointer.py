from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from resume_agent.core.config import settings


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[AsyncSqliteSaver, None]:
    """Yield an AsyncSqliteSaver connected to the checkpoints DB for crash recovery."""
    Path(settings.CHECKPOINT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINT_DB_PATH) as checkpointer:
        yield checkpointer
