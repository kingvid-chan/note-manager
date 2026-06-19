"""pytest 全局 fixtures — 内存 SQLite + TestClient + 认证辅助。

每个测试函数获得完全隔离的数据库（建表 → 使用 → 删表）。
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.note_manager.database import Base, get_db
from src.note_manager.main import app
from src.note_manager.models import User
from src.note_manager.services.auth_service import hash_password

# ═════════════════════════════════════════════════════════════════
# Engine — 每个测试函数一个全新的内存 SQLite
# ═════════════════════════════════════════════════════════════════

@pytest.fixture()
def engine():
    """内存 SQLite 引擎 — StaticPool 确保所有连接指向同一内存库。

    所有依赖该 fixture 的测试共享同一个 engine 实例（per-function scope），
    通过 create_all / drop_all 保证完全隔离。
    """
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite 默认不启用外键约束，必须手动开启
    @event.listens_for(e, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=e)
    yield e
    Base.metadata.drop_all(bind=e)


# ═════════════════════════════════════════════════════════════════
# DB Session — 用于直接操作数据库的模型测试
# ═════════════════════════════════════════════════════════════════

@pytest.fixture()
def db(engine):
    """直接数据库会话 — 用于模型层和工厂函数测试。"""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════
# TestClient — FastAPI 测试客户端，依赖 override 指向内存库
# ═════════════════════════════════════════════════════════════════

@pytest.fixture()
def client(engine):
    """FastAPI TestClient — get_db 依赖被替换为内存 SQLite 会话。

    每次请求创建新的 DB 会话，请求结束自动关闭。
    所有测试函数内的请求共享同一个 engine（内存库），
    因此数据跨请求可见（如同真实应用）。
    """
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ═════════════════════════════════════════════════════════════════
# 认证辅助
# ═════════════════════════════════════════════════════════════════

_TEST_USER = {
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "testpass123",
}

_OTHER_USER = {
    "username": "otheruser",
    "email": "other@example.com",
    "password": "otherpass123",
}


@pytest.fixture()
def auth_headers(client):
    """注册 testuser → 登录 → 返回 Authorization header。

    所有需要 JWT 认证的请求传入 ``headers=auth_headers`` 即可。
    """
    client.post("/projects/note-manager/api/auth/register", json=_TEST_USER)
    resp = client.post("/projects/note-manager/api/auth/login", json={
        "username": _TEST_USER["username"],
        "password": _TEST_USER["password"],
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers_other(client):
    """注册 otheruser → 登录 → 返回另一个用户的 auth header。

    用于所有权隔离测试（例如确保 user A 不能操作 user B 的笔记）。
    """
    client.post("/projects/note-manager/api/auth/register", json=_OTHER_USER)
    resp = client.post("/projects/note-manager/api/auth/login", json={
        "username": _OTHER_USER["username"],
        "password": _OTHER_USER["password"],
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ═════════════════════════════════════════════════════════════════
# 测试用户对象（直接 DB 访问，跳过 API）
# ═════════════════════════════════════════════════════════════════

@pytest.fixture()
def test_user(db):
    """直接在数据库中创建 testuser 并返回 User ORM 对象。"""
    user = User(
        username=_TEST_USER["username"],
        email=_TEST_USER["email"],
        password_hash=hash_password(_TEST_USER["password"]),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def other_user(db):
    """直接在数据库中创建 otheruser 并返回 User ORM 对象。"""
    user = User(
        username=_OTHER_USER["username"],
        email=_OTHER_USER["email"],
        password_hash=hash_password(_OTHER_USER["password"]),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
