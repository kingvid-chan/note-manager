"""数据库引擎、会话工厂和依赖注入。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


# SQLite 引擎 — WAL 模式提升并发读性能
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """每次连接时启用 WAL 日志模式。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


def get_db():
    """FastAPI 依赖 — 每个请求一个数据库会话，结束时自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
