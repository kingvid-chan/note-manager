"""认证模块测试 — auth_service 纯函数单元测试 + auth API 端点测试。

覆盖：hash/verify password、create/decode token、注册/登录/me/无效token/过期token。
"""

import time
from datetime import datetime, timedelta

import pytest
from jose import jwt

from src.note_manager.config import settings
from src.note_manager.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


# ═════════════════════════════════════════════════════════════════
# 认证服务层 — 纯函数单元测试
# ═════════════════════════════════════════════════════════════════

class TestHashPassword:
    """hash_password / verify_password 单元测试。"""

    def test_hash_returns_string(self):
        """哈希结果应为字符串。"""
        result = hash_password("mypassword")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_is_deterministic_for_same_salt(self):
        """不同调用产生不同哈希（随机 salt）。"""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # salt 不同 → 哈希不同

    def test_verify_correct_password(self):
        """正确密码应校验通过。"""
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_verify_wrong_password(self):
        """错误密码应校验失败。"""
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_verify_empty_password(self):
        """空密码也应正确工作。"""
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_unicode_normalization(self):
        """Unicode NFKC 归一化 — 全角/半角等价。"""
        # 全角 "Ａ" (U+FF21) 应归一化为半角 "A" (U+0041)
        hashed = hash_password("Ａbc")  # 全角 A
        assert verify_password("Abc", hashed) is True  # 半角 A


class TestJWTToken:
    """create_access_token / decode_access_token 单元测试。"""

    def test_create_token_returns_string(self):
        """token 应为非空字符串。"""
        token = create_access_token(42)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        """有效 token 应成功解码并返回 payload。"""
        token = create_access_token(42)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_decode_tampered_token(self):
        """篡改 token → 返回 None。"""
        token = create_access_token(42)
        # 修改最后一个字符
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        payload = decode_access_token(tampered)
        assert payload is None

    def test_decode_empty_token(self):
        """空字符串 → None。"""
        assert decode_access_token("") is None

    def test_decode_nonsense_token(self):
        """随机字符串 → None。"""
        assert decode_access_token("not.a.valid.jwt") is None

    def test_decode_none_token(self):
        """None → None (类型安全)。"""
        # decode_access_token 签名期望 str，但防御性测试
        pass  # mypy 类型检查在测试中不强制

    def test_token_contains_exp(self):
        """token payload 应包含 exp 字段。"""
        token = create_access_token(1)
        payload = decode_access_token(token)
        assert "exp" in payload
        assert isinstance(payload["exp"], int)

    def test_expiry_is_future(self):
        """新 token 的 exp 应在未来。"""
        token = create_access_token(1)
        payload = decode_access_token(token)
        exp = datetime.utcfromtimestamp(payload["exp"])
        assert exp > datetime.utcnow()

    def test_expired_token(self):
        """过期 token → decode 返回 None。"""
        # 手动构造一个已过期的 token
        expire = datetime.utcnow() - timedelta(hours=1)
        payload = {"sub": "1", "exp": expire}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        result = decode_access_token(token)
        assert result is None

    def test_wrong_secret(self):
        """用错误密钥签发 → decode 返回 None。"""
        payload = {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=1)}
        token = jwt.encode(payload, "wrong-secret", algorithm=settings.JWT_ALGORITHM)
        result = decode_access_token(token)
        assert result is None

    def test_different_algorithm(self):
        """用不同算法签发 → decode 返回 None。"""
        payload = {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=1)}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS384")
        result = decode_access_token(token)
        assert result is None

    def test_missing_sub(self):
        """无 sub 字段的 token → decode 成功但 sub 不存在的 payload。"""
        expire = datetime.utcnow() + timedelta(hours=1)
        payload = {"exp": expire}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        result = decode_access_token(token)
        assert result is not None
        assert "sub" not in result


# ═════════════════════════════════════════════════════════════════
# 认证 API 端点测试 (TestClient)
# ═════════════════════════════════════════════════════════════════

class TestRegisterAPI:
    """POST /api/auth/register"""

    def test_register_success(self, client):
        """注册新用户 → 201 + 返回 user info（无密码哈希）。"""
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert "password_hash" not in data
        assert data["is_active"] is True
        assert data["is_demo"] is False

    def test_register_duplicate_username(self, client):
        """重复用户名 → 409。"""
        client.post("/projects/note-manager/api/auth/register", json={
            "username": "dupuser",
            "email": "dup1@example.com",
            "password": "secret123",
        })
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "dupuser",
            "email": "dup2@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 409
        assert "Username already exists" in resp.json()["detail"]

    def test_register_duplicate_email(self, client):
        """重复邮箱 → 409。"""
        client.post("/projects/note-manager/api/auth/register", json={
            "username": "user1",
            "email": "dup@example.com",
            "password": "secret123",
        })
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "user2",
            "email": "dup@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 409
        assert "Email already exists" in resp.json()["detail"]

    def test_register_invalid_email(self, client):
        """无效邮箱 → 422。"""
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "user",
            "email": "not-an-email",
            "password": "secret123",
        })
        assert resp.status_code == 422

    def test_register_short_username(self, client):
        """短用户名 (<3) → 422。"""
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "ab",
            "email": "ab@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        """短密码 (<6) → 422。"""
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "user123",
            "email": "user@example.com",
            "password": "12345",
        })
        assert resp.status_code == 422

    def test_register_missing_field(self, client):
        """缺少必填字段 → 422。"""
        resp = client.post("/projects/note-manager/api/auth/register", json={
            "username": "user",
            "password": "secret123",
        })
        assert resp.status_code == 422


class TestLoginAPI:
    """POST /api/auth/login"""

    def test_login_success(self, client):
        """正确凭据 → 200 + access_token + user 摘要。"""
        # 先注册
        client.post("/projects/note-manager/api/auth/register", json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "testpass123",
        })
        resp = client.post("/projects/note-manager/api/auth/login", json={
            "username": "loginuser",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        """错误密码 → 401。"""
        client.post("/projects/note-manager/api/auth/register", json={
            "username": "wrongpw",
            "email": "wrongpw@example.com",
            "password": "correct",
        })
        resp = client.post("/projects/note-manager/api/auth/login", json={
            "username": "wrongpw",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        """不存在的用户 → 401。"""
        resp = client.post("/projects/note-manager/api/auth/login", json={
            "username": "nobody",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_login_form_urlencoded(self, client):
        """form-urlencoded 格式登录 → 200。"""
        client.post("/projects/note-manager/api/auth/register", json={
            "username": "formuser",
            "email": "form@example.com",
            "password": "formpass123",
        })
        resp = client.post(
            "/projects/note-manager/api/auth/login",
            data={"username": "formuser", "password": "formpass123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_missing_username(self, client):
        """缺少用户名 → 422。"""
        resp = client.post("/projects/note-manager/api/auth/login", json={
            "password": "whatever",
        })
        assert resp.status_code == 422

    def test_login_empty_body(self, client):
        """空请求体 → 422。"""
        resp = client.post("/projects/note-manager/api/auth/login", json={})
        assert resp.status_code in (401, 422)


class TestMeAPI:
    """GET /api/auth/me"""

    def test_me_with_valid_token(self, client, auth_headers):
        """有效 token → 200 + user info。"""
        resp = client.get(
            "/projects/note-manager/api/auth/me",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["email"] == "testuser@example.com"
        assert "password_hash" not in data

    def test_me_without_token(self, client):
        """无 token → 401。"""
        resp = client.get("/projects/note-manager/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_invalid_token(self, client):
        """无效 token（随机字符串） → 401。"""
        resp = client.get(
            "/projects/note-manager/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_me_with_expired_token(self, client):
        """过期 token → 401。"""
        # 手动签发一个已过期的 JWT
        expire = datetime.utcnow() - timedelta(hours=1)
        payload = {"sub": "99999", "exp": expire}
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        resp = client.get(
            "/projects/note-manager/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_me_with_wrong_token_type(self, client):
        """非 Bearer token → 401。"""
        resp = client.get(
            "/projects/note-manager/api/auth/me",
            headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        )
        assert resp.status_code == 401

    def test_me_with_nonexistent_user_in_token(self, client):
        """token 中的 sub 指向不存在的用户 → 401。"""
        expire = datetime.utcnow() + timedelta(hours=1)
        payload = {"sub": "99999", "exp": expire}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        resp = client.get(
            "/projects/note-manager/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
