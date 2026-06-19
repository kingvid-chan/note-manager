"""标签 API 集成测试 — 创建/列表/添加/移除标签。

使用 FastAPI TestClient + dependency_override（通过 conftest.py 的 ``client`` fixture）。
全部端点需要 JWT 认证（通过 ``auth_headers`` fixture）。

注意：标签没有独立的 POST /api/tags/ 端点，
标签通过 POST /api/notes/{note_id}/tags 自动创建（get_or_create_tag）。
"""

import pytest


NOTES = "/projects/note-manager/api/notes/"
TAGS = "/projects/note-manager/api/tags/"


# ═════════════════════════════════════════════════════════════════
# 标签创建（通过 notes/{id}/tags 隐式创建）
# ═════════════════════════════════════════════════════════════════

class TestCreateTag:
    """标签通过 POST /api/notes/{note_id}/tags 自动创建。"""

    def test_create_tag_via_note(self, client, auth_headers):
        """向笔记添加新标签 → 自动创建标签 → 201。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()

        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "python"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "python"
        assert data["id"] is not None
        assert data["note_count"] == 1  # 已关联到当前笔记

    def test_create_duplicate_tag_same_user(self, client, auth_headers):
        """同一用户重复添加同名标签 — 不创建重复标签，复用已有。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()

        # 第一次添加 → 创建标签
        r1 = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "dup"},
            headers=auth_headers,
        )
        tag_id = r1.json()["id"]

        # 第二次添加同名标签到另一笔记 → 复用已有标签
        note2 = client.post(NOTES, json={"title": "N2"}, headers=auth_headers).json()
        r2 = client.post(
            f"{NOTES}{note2['id']}/tags",
            json={"name": "dup"},
            headers=auth_headers,
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == tag_id  # 复用了同一个标签

    def test_create_empty_name(self, client, auth_headers):
        """空标签名 → 422。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()
        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_long_name(self, client, auth_headers):
        """标签名 > 64 字符 → 422。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()
        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "x" * 65},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_unauthorized(self, client):
        """无 token → 401。"""
        resp = client.post(f"{NOTES}1/tags", json={"name": "tag"})
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════
# GET /api/tags/ — 标签列表（含使用计数）
# ═════════════════════════════════════════════════════════════════

class TestListTags:
    """GET /api/tags/"""

    def test_list_empty(self, client, auth_headers):
        """新用户无标签 → 空列表。"""
        resp = client.get(TAGS, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_list_with_items(self, client, auth_headers):
        """创建标签后列表应包含它们。"""
        # 通过向笔记添加标签来创建
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()
        client.post(f"{NOTES}{note['id']}/tags", json={"name": "a"}, headers=auth_headers)
        client.post(f"{NOTES}{note['id']}/tags", json={"name": "b"}, headers=auth_headers)

        resp = client.get(TAGS, headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        names = [t["name"] for t in items]
        assert "a" in names
        assert "b" in names

    def test_list_with_note_count(self, client, auth_headers):
        """标签列表应含 note_count 使用计数。"""
        # 创建 2 个笔记，都关联同一个标签
        n1 = client.post(NOTES, json={"title": "N1"}, headers=auth_headers).json()
        n2 = client.post(NOTES, json={"title": "N2"}, headers=auth_headers).json()

        r = client.post(f"{NOTES}{n1['id']}/tags", json={"name": "shared"}, headers=auth_headers)
        tag_id = r.json()["id"]

        client.post(f"{NOTES}{n2['id']}/tags", json={"name": "shared"}, headers=auth_headers)

        # 检查计数
        resp = client.get(TAGS, headers=auth_headers)
        items = resp.json()["items"]
        tag = next((t for t in items if t["id"] == tag_id), None)
        assert tag is not None
        assert tag["note_count"] == 2

    def test_list_isolated_by_user(self, client, auth_headers, auth_headers_other):
        """标签按用户隔离 — 不同用户的标签不互相可见。"""
        n_a = client.post(NOTES, json={"title": "A"}, headers=auth_headers).json()
        n_b = client.post(NOTES, json={"title": "B"}, headers=auth_headers_other).json()

        client.post(f"{NOTES}{n_a['id']}/tags", json={"name": "user-a-tag"}, headers=auth_headers)
        client.post(f"{NOTES}{n_b['id']}/tags", json={"name": "user-b-tag"}, headers=auth_headers_other)

        # user A 只能看到自己的
        resp = client.get(TAGS, headers=auth_headers)
        names = [t["name"] for t in resp.json()["items"]]
        assert "user-a-tag" in names
        assert "user-b-tag" not in names


# ═════════════════════════════════════════════════════════════════
# POST /api/notes/{id}/tags — 为笔记添加标签
# ═════════════════════════════════════════════════════════════════

class TestAddTagToNote:
    """POST /api/notes/{note_id}/tags"""

    def test_add_tag_to_note(self, client, auth_headers):
        """为笔记添加已有标签 → 201。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()

        # 第一次添加 → 创建标签
        r1 = client.post(f"{NOTES}{note['id']}/tags", json={"name": "label"}, headers=auth_headers)
        tag_id = r1.json()["id"]
        assert r1.status_code == 201

        # 再创建一个笔记，添加同一个标签
        note2 = client.post(NOTES, json={"title": "N2"}, headers=auth_headers).json()
        r2 = client.post(f"{NOTES}{note2['id']}/tags", json={"name": "label"}, headers=auth_headers)
        assert r2.status_code == 201
        assert r2.json()["id"] == tag_id
        assert r2.json()["note_count"] >= 2

    def test_add_new_tag_via_note(self, client, auth_headers):
        """添加还不存在的标签 → 自动创建 → 201。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()

        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "brand-new"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "brand-new"

    def test_add_tag_to_nonexistent_note(self, client, auth_headers):
        """添加到不存在的笔记 → 404。"""
        resp = client.post(
            f"{NOTES}99999/tags",
            json={"name": "tag"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_add_tag_not_owner(self, client, auth_headers, auth_headers_other):
        """非所有者添加标签 → 403。"""
        note = client.post(NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "hack"},
            headers=auth_headers_other,
        )
        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════
# DELETE /api/notes/{note_id}/tags/{tag_id} — 移除标签关联
# ═════════════════════════════════════════════════════════════════

class TestRemoveTagFromNote:
    """DELETE /api/notes/{note_id}/tags/{tag_id}"""

    def test_remove_tag_from_note(self, client, auth_headers):
        """移除标签关联 → 204。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()

        # 添加标签
        r = client.post(f"{NOTES}{note['id']}/tags", json={"name": "temp"}, headers=auth_headers)
        tag_id = r.json()["id"]

        # 移除
        resp = client.delete(
            f"{NOTES}{note['id']}/tags/{tag_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    def test_remove_nonexistent_link(self, client, auth_headers):
        """移除不存在的关联 → 404。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()
        resp = client.delete(
            f"{NOTES}{note['id']}/tags/99999",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_remove_tag_not_owner(self, client, auth_headers, auth_headers_other):
        """非所有者移除标签 → 403。"""
        note = client.post(NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        r = client.post(f"{NOTES}{note['id']}/tags", json={"name": "mine"}, headers=auth_headers)
        tag_id = r.json()["id"]

        resp = client.delete(
            f"{NOTES}{note['id']}/tags/{tag_id}",
            headers=auth_headers_other,
        )
        assert resp.status_code == 403
