from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
)
import os
import threading

thread_data = threading.local()


class Engine:
    def __init__(self, db_url: str, *, echo: bool = False):
        self._db_url = db_url
        self._echo = echo
        self._engine: AsyncEngine = create_async_engine(db_url, echo=echo)
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(self._engine)
        thread_data.db_engine = self._engine

    def create_session(self):
        if not hasattr(thread_data, 'db_engine'):
            self._engine = create_async_engine(self._db_url, echo=self._echo)
            self._sessionmaker = async_sessionmaker(self._engine)
            thread_data.db_engine = self._engine
        return self._sessionmaker()


async_db_url = os.environ['IW_DB_URL'].replace('postgresql://', 'postgresql+asyncpg://')
db_engine = Engine(async_db_url)
