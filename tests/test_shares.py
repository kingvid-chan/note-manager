"""分享模块测试 — 创建/过期/列表/撤销/公开访问/所有权检查。

使用 FastAPI TestClient + dependency_override（通过 conftest.py 的 ``client`` fixture）。
"""

import time
from datetime import datetime, timedelta

import pytest

from tests.factories import create_test_user, create_test_note, create_test_share


NOTES = "/projects/note-manager/api/notes/"
SHARES = "/projects/note-manager/api/shares/"
PUBLIC = "/projects/note-manager/api/public/notes/"


# ═════════════════════════════════════════════════════════════════
# 创建分享链接
# ═════════════════════════════════════════════════════════════════

class TestCreateShare:
    """create_share — POST /api/notes/{note_id}/share"""

    def test_create_share(self, client, auth_headers):
        """创建分享链接 → 201 + token + url。"""
        note = client.post(NOTES, json={"title": "Share Me"}, headers=auth_headers).json()

        resp = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) == 32  # uuid4 hex
        assert data["url"] == f"/projects/note-manager/share/{data['token']}"
        assert data["note_id"] == note["id"]
        assert data["note_title"] == "Share Me"
        assert data["is_active"] is True
        assert data["created_at"] is not None

    def test_create_share_with_expiry(self, client, auth_headers):
        """创建含过期时间的分享链接 → 201 + expires_at 不为空。"""
        note = client.post(NOTES, json={"title": "Expiring"}, headers=auth_headers).json()

        resp = client.post(
            f"{NOTES}{note['id']}/share",
            json={"expires_in_hours": 48},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expires_at"] is not None
        # expires_at 应约为当前时间 + 48 小时
        expires = datetime.fromisoformat(data["expires_at"])
        delta = expires - datetime.utcnow()
        assert timedelta(hours=47) < delta < timedelta(hours=49)

    def test_create_share_no_expiry(self, client, auth_headers):
        """创建永不过期的分享链接 → 201 + expires_at 为 null。"""
        note = client.post(NOTES, json={"title": "Forever"}, headers=auth_headers).json()

        resp = client.post(
            f"{NOTES}{note['id']}/share",
            json={"expires_in_hours": None},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["expires_at"] is None


# ═════════════════════════════════════════════════════════════════
# 列出分享
# ═════════════════════════════════════════════════════════════════

class TestListShares:
    """list — GET /api/shares/ 返回当前用户的所有分享。"""

    def test_list_shares(self, client, auth_headers):
        """创建多个分享后列表应包含它们。"""
        note = client.post(NOTES, json={"title": "Shared"}, headers=auth_headers).json()
        client.post(f"{NOTES}{note['id']}/share", json={}, headers=auth_headers)
        client.post(f"{NOTES}{note['id']}/share", json={}, headers=auth_headers)

        resp = client.get(SHARES, headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

    def test_list_shares_isolation(self, client, auth_headers, auth_headers_other):
        """分享列表按用户隔离 — 不同用户互不可见。"""
        n_a = client.post(NOTES, json={"title": "A"}, headers=auth_headers).json()
        n_b = client.post(NOTES, json={"title": "B"}, headers=auth_headers_other).json()

        client.post(f"{NOTES}{n_a['id']}/share", json={}, headers=auth_headers)
        client.post(f"{NOTES}{n_b['id']}/share", json={}, headers=auth_headers_other)

        resp_a = client.get(SHARES, headers=auth_headers)
        assert len(resp_a.json()["items"]) == 1


# ═════════════════════════════════════════════════════════════════
# 撤销分享
# ═════════════════════════════════════════════════════════════════

class TestRevokeShare:
    """revoke — DELETE /api/shares/{share_id} 撤销分享链接。"""

    def test_revoke_share(self, client, auth_headers):
        """撤销分享 → 204。"""
        note = client.post(NOTES, json={"title": "Revoke Me"}, headers=auth_headers).json()
        share = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        ).json()

        resp = client.delete(f"{SHARES}{share['id']}", headers=auth_headers)
        assert resp.status_code == 204

    def test_revoke_then_public_404(self, client, auth_headers):
        """撤销后公开访问 → 404。"""
        note = client.post(NOTES, json={"title": "Gone"}, headers=auth_headers).json()
        share = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        ).json()

        client.delete(f"{SHARES}{share['id']}", headers=auth_headers)

        resp = client.get(f"{PUBLIC}{share['token']}")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# 公开访问
# ═════════════════════════════════════════════════════════════════

class TestPublicAccess:
    """public_access — GET /api/public/notes/{token} 无需认证的公开只读接口。"""

    def test_public_access_share(self, client, auth_headers):
        """有效 token → 200 + 笔记完整内容 + 作者信息。"""
        note = client.post(NOTES, json={
            "title": "Public Note",
            "content_md": "# Hello World\nThis is **markdown**.",
        }, headers=auth_headers).json()
        share = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        ).json()

        resp = client.get(f"{PUBLIC}{share['token']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Public Note"
        assert data["content_md"] == "# Hello World\nThis is **markdown**."
        assert data["author"]["username"] == "testuser"
        # 不应泄露邮箱等敏感信息
        assert "email" not in data.get("author", {})
        assert "password" not in data.get("author", {})

    def test_public_access_expired(self, db, client):
        """过期分享链接 → 404。"""
        # 用 factory 直接在 DB 创建过期分享
        user = create_test_user(db)
        note = create_test_note(db, user_id=user.id, title="Expired Note")

        share = create_test_share(db, note_id=note.id, user_id=user.id)
        # 手动设置 expires_at 为过去时间
        share.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        resp = client.get(f"{PUBLIC}{share.token}")
        assert resp.status_code == 404

    def test_public_access_invalid_token(self, client):
        """不存在的 token → 404。"""
        resp = client.get(f"{PUBLIC}nonexistent-token-12345")
        assert resp.status_code == 404

    def test_public_access_revoked(self, client, auth_headers):
        """已撤销的分享 → 404。"""
        note = client.post(NOTES, json={"title": "Revoked"}, headers=auth_headers).json()
        share = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        ).json()

        client.delete(f"{SHARES}{share['id']}", headers=auth_headers)

        resp = client.get(f"{PUBLIC}{share['token']}")
        assert resp.status_code == 404

    def test_public_access_no_auth(self, client, auth_headers):
        """公开接口无需认证 — 不传任何 header。"""
        note = client.post(NOTES, json={"title": "Open"}, headers=auth_headers).json()
        share = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        ).json()

        # 不带 Authorization header
        resp = client.get(f"{PUBLIC}{share['token']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Open"


# ═════════════════════════════════════════════════════════════════
# 所有权检查
# ═════════════════════════════════════════════════════════════════

class TestShareNotOwner:
    """not_owner — 非所有者不能操作他人的分享。"""

    def test_share_not_owner_create(self, client, auth_headers, auth_headers_other):
        """非所有者无法为他人笔记创建分享 → 403。"""
        note = client.post(NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        resp = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers_other,
        )
        assert resp.status_code == 403

    def test_share_not_owner_revoke(self, client, auth_headers, auth_headers_other):
        """非所有者无法撤销他人的分享 → 403。"""
        note = client.post(NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        share = client.post(
            f"{NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        ).json()

        resp = client.delete(
            f"{SHARES}{share['id']}",
            headers=auth_headers_other,
        )
        assert resp.status_code == 403
