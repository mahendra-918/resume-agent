from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from resume_agent.core.config import settings


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[AsyncSqliteSaver, None]:
    """Yield an AsyncSqliteSaver connected to the project DB for crash recovery."""
    async with AsyncSqliteSaver.from_conn_string(settings.DB_PATH) as checkpointer:
        yield checkpointer
