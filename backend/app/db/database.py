"""
SQLite 数据库连接配置 (SQLAlchemy 2.0 Async)
开启 WAL 模式以提升并发性能
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from sqlalchemy.pool import NullPool

from app.core.config import settings

# 创建异步引擎 (禁用连接池以避免 SQLite 线程检查问题)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # 开发模式下打印 SQL 日志
    connect_args={"check_same_thread": False},  # SQLite 特有配置
    poolclass=NullPool,  # 对于 SQLite，使用 NullPool 避免连接池问题
)


# 开启 WAL 模式 (Write-Ahead Logging) 提升并发性能
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """在每次连接时设置 SQLite PRAGMA"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 防止在 commit 后对象失效
    autoflush=False,
    autocommit=False,
)

# 声明基类
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    数据库会话依赖注入函数
    用于 FastAPI 路由中的 Depends()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    初始化数据库表结构
    在应用启动时调用
    """
    async with engine.begin() as conn:
        # 创建所有表 (基于 Base.metadata)
        await conn.run_sync(Base.metadata.create_all)
        # 兼容已存在库：确保“每用户仅一个默认地址”的部分唯一索引存在
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_default_address "
                "ON user_addresses (user_id) WHERE is_default = 1"
            )
        )
