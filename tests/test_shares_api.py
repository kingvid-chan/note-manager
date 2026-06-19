"""分享 API 集成测试 — 创建/列表/撤销/公开查看。

使用 FastAPI TestClient + dependency_override（通过 conftest.py 的 ``client`` fixture）。
"""

import pytest


# ═════════════════════════════════════════════════════════════════
# POST /api/notes/{note_id}/share — 创建分享链接
# ═════════════════════════════════════════════════════════════════

class TestCreateShare:
    """POST /api/notes/{note_id}/share"""

    NOTES = "/projects/note-manager/api/notes/"

    def test_create_share(self, client, auth_headers):
        """创建分享链接 → 201 + token + url。"""
        # 先创建笔记
        note = client.post(self.NOTES, json={"title": "Share Me"}, headers=auth_headers).json()

        resp = client.post(
            f"{self.NOTES}{note['id']}/share",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["token"] is not None
        assert len(data["token"]) == 32  # uuid4 hex
        assert data["url"] == f"/projects/note-manager/share/{data['token']}"
        assert data["note_id"] == note["id"]
        assert data["note_title"] == "Share Me"
        assert data["is_active"] is True

    def test_create_share_with_expiry(self, client, auth_headers):
        """创建分享链接含过期时间 → 201。"""
        note = client.post(self.NOTES, json={"title": "Expiring"}, headers=auth_headers).json()

        resp = client.post(
            f"{self.NOTES}{note['id']}/share",
            json={"expires_in_hours": 48},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expires_at"] is not None  # 有过期时间

    def test_create_share_no_expiry(self, client, auth_headers):
        """创建永不过期的分享链接 → 201。"""
        note = client.post(self.NOTES, json={"title": "Forever"}, headers=auth_headers).json()

        resp = client.post(
            f"{self.NOTES}{note['id']}/share",
            json={"expires_in_hours": None},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["expires_at"] is None

    def test_create_share_nonexistent_note(self, client, auth_headers):
        """为不存在的笔记创建分享 → 404。"""
        resp = client.post(f"{self.NOTES}99999/share", json={}, headers=auth_headers)
        assert resp.status_code == 404

    def test_create_share_not_owner(self, client, auth_headers, auth_headers_other):
        """非所有者为笔记创建分享 → 403。"""
        note = client.post(self.NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        resp = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers_other)
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════
# GET /api/shares/ — 用户分享列表
# ═════════════════════════════════════════════════════════════════

class TestListShares:
    """GET /api/shares/"""

    NOTES = "/projects/note-manager/api/notes/"
    SHARES = "/projects/note-manager/api/shares/"

    def test_list_empty(self, client, auth_headers):
        """新用户无分享 → 空列表。"""
        resp = client.get(self.SHARES, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_list_with_items(self, client, auth_headers):
        """创建分享后列表应包含它们。"""
        note = client.post(self.NOTES, json={"title": "Shared"}, headers=auth_headers).json()
        client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers)
        client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers)

        resp = client.get(self.SHARES, headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

    def test_list_isolated_by_user(self, client, auth_headers, auth_headers_other):
        """分享列表按用户隔离。"""
        note_a = client.post(self.NOTES, json={"title": "A's"}, headers=auth_headers).json()
        note_b = client.post(self.NOTES, json={"title": "B's"}, headers=auth_headers_other).json()

        client.post(f"{self.NOTES}{note_a['id']}/share", json={}, headers=auth_headers)
        client.post(f"{self.NOTES}{note_b['id']}/share", json={}, headers=auth_headers_other)

        # user A 只能看到自己的
        resp = client.get(self.SHARES, headers=auth_headers)
        assert len(resp.json()["items"]) == 1


# ═════════════════════════════════════════════════════════════════
# DELETE /api/shares/{share_id} — 撤销分享
# ═════════════════════════════════════════════════════════════════

class TestRevokeShare:
    """DELETE /api/shares/{share_id}"""

    NOTES = "/projects/note-manager/api/notes/"
    SHARES = "/projects/note-manager/api/shares/"

    def test_revoke_share(self, client, auth_headers):
        """撤销分享 → 204。"""
        note = client.post(self.NOTES, json={"title": "Revoke Me"}, headers=auth_headers).json()
        share = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers).json()

        resp = client.delete(f"{self.SHARES}{share['id']}", headers=auth_headers)
        assert resp.status_code == 204

    def test_revoke_then_public_access_fails(self, client, auth_headers):
        """撤销后公开访问 → 404。"""
        note = client.post(self.NOTES, json={"title": "Gone"}, headers=auth_headers).json()
        share = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers).json()

        # 撤销
        client.delete(f"{self.SHARES}{share['id']}", headers=auth_headers)

        # 公开访问应失败
        resp = client.get(f"/projects/note-manager/api/public/notes/{share['token']}")
        assert resp.status_code == 404

    def test_revoke_not_owner(self, client, auth_headers, auth_headers_other):
        """非所有者撤销分享 → 403。"""
        note = client.post(self.NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        share = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers).json()

        resp = client.delete(f"{self.SHARES}{share['id']}", headers=auth_headers_other)
        assert resp.status_code == 403

    def test_revoke_nonexistent(self, client, auth_headers):
        """撤销不存在的分享 → 404。"""
        resp = client.delete(f"{self.SHARES}99999", headers=auth_headers)
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# GET /api/public/notes/{token} — 公开查看分享笔记
# ═════════════════════════════════════════════════════════════════

class TestPublicAccess:
    """GET /api/public/notes/{token} — 无需认证的公开接口。"""

    NOTES = "/projects/note-manager/api/notes/"
    SHARES = "/projects/note-manager/api/shares/"

    def test_public_access_valid_token(self, client, auth_headers):
        """有效 token → 200 + 笔记内容 + 作者信息。"""
        note = client.post(self.NOTES, json={
            "title": "Public", "content_md": "# Hello"
        }, headers=auth_headers).json()
        share = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers).json()

        resp = client.get(f"/projects/note-manager/api/public/notes/{share['token']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Public"
        assert data["content_md"] == "# Hello"
        assert data["author"]["username"] == "testuser"
        # 不应包含敏感字段
        assert "email" not in data.get("author", {})

    def test_public_access_invalid_token(self, client):
        """不存在的 token → 404。"""
        resp = client.get("/projects/note-manager/api/public/notes/nonexistent-token")
        assert resp.status_code == 404

    def test_public_access_no_auth_required(self, client, auth_headers):
        """公开接口无需认证。"""
        note = client.post(self.NOTES, json={"title": "Open"}, headers=auth_headers).json()
        share = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers).json()

        # 不带任何认证 header
        resp = client.get(f"/projects/note-manager/api/public/notes/{share['token']}")
        assert resp.status_code == 200

    def test_public_access_revoked_share(self, client, auth_headers):
        """已撤销的分享 → 404。"""
        note = client.post(self.NOTES, json={"title": "Revoked"}, headers=auth_headers).json()
        share = client.post(f"{self.NOTES}{note['id']}/share", json={}, headers=auth_headers).json()

        # 撤销
        client.delete(f"{self.SHARES}{share['id']}", headers=auth_headers)

        # 公开访问应失败
        resp = client.get(f"/projects/note-manager/api/public/notes/{share['token']}")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# 健康检查
# ═════════════════════════════════════════════════════════════════

class TestHealthCheck:
    """健康检查端点 — 无需认证。"""

    def test_healthz(self, client):
        """GET /healthz → 200 + ok。"""
        resp = client.get("/projects/note-manager/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
