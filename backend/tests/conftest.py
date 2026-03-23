"""
后端测试公共夹具

说明：
- 不改动业务源码，使用临时 SQLite 数据库执行单元测试
- 保持与生产一致的关键 SQLite 配置（WAL、foreign_keys、busy_timeout）
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# 强制测试环境变量，避免本机环境污染（如 DEBUG=release 导致 bool 解析失败）
os.environ["DEBUG"] = "false"
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.db.database import Base
from app.db.models import Product, User, UserAddress


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@pytest_asyncio.fixture
async def db_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    """
    每个测试独立 SQLite 文件，确保事务与并发行为可重复。
    """
    db_file = tmp_path / "unit_test.db"
    database_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    engine = create_async_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession) -> User:
    user = User(
        username="buyer_1",
        email="buyer_1@example.com",
        password_hash="hashed",
        role="client",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_second_user(db_session: AsyncSession) -> User:
    user = User(
        username="buyer_2",
        email="buyer_2@example.com",
        password_hash="hashed",
        role="client",
        token_version=1,
        is_active=1,
        failed_login_attempts=0,
        created_at=_now_iso(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seed_product(db_session: AsyncSession) -> Product:
    product = Product(
        name="测试降噪耳机",
        description="40dB 主动降噪",
        price=399.0,
        stock=10,
        status="on_sale",
        created_at=_now_iso(),
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest_asyncio.fixture
async def seed_address(db_session: AsyncSession, seed_user: User) -> UserAddress:
    address = UserAddress(
        user_id=seed_user.id,
        receiver_name="张三",
        phone="13812345678",
        province="上海市",
        city="上海市",
        district="浦东新区",
        detail_address="世纪大道 100 号",
        is_default=1,
        created_at=_now_iso(),
    )
    db_session.add(address)
    await db_session.commit()
    await db_session.refresh(address)
    return address
