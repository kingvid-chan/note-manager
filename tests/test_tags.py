"""标签模块测试 — 创建/重复检测/列表/删除/所有权检查。

使用 FastAPI TestClient + dependency_override（通过 conftest.py 的 ``client`` fixture）。
标签通过 POST /api/notes/{note_id}/tags 自动创建（get_or_create_tag）。
"""

import pytest


NOTES = "/projects/note-manager/api/notes/"
TAGS = "/projects/note-manager/api/tags/"


# ═════════════════════════════════════════════════════════════════
# 标签创建
# ═════════════════════════════════════════════════════════════════

class TestCreateTag:
    """create_tag — 通过 POST /api/notes/{note_id}/tags 隐式创建标签。"""

    def test_create_tag(self, client, auth_headers):
        """向笔记添加新标签 → 自动创建 → 201。"""
        note = client.post(NOTES, json={"title": "Test Note"}, headers=auth_headers).json()

        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "python"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "python"
        assert isinstance(data["id"], int)
        assert data["note_count"] == 1


class TestDuplicateTag:
    """duplicate — 同一用户重复添加同名标签应复用已有标签。"""

    def test_create_duplicate_tag(self, client, auth_headers):
        """重复添加同名标签 → 不创建新记录，复用已有标签 ID。"""
        note1 = client.post(NOTES, json={"title": "Note 1"}, headers=auth_headers).json()
        note2 = client.post(NOTES, json={"title": "Note 2"}, headers=auth_headers).json()

        # 第一次添加 → 创建新标签
        r1 = client.post(
            f"{NOTES}{note1['id']}/tags",
            json={"name": "work"},
            headers=auth_headers,
        )
        assert r1.status_code == 201
        tag_id = r1.json()["id"]

        # 第二次添加同名标签到另一个笔记 → 复用标签
        r2 = client.post(
            f"{NOTES}{note2['id']}/tags",
            json={"name": "work"},
            headers=auth_headers,
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == tag_id  # 复用了同一个标签

    def test_duplicate_tag_case_sensitive(self, client, auth_headers):
        """大小写不同的标签视为不同标签。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()

        r1 = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "Work"},
            headers=auth_headers,
        )
        r2 = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "work"},
            headers=auth_headers,
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        # 由于 case-sensitive compare，应创建两个不同标签
        assert r1.json()["id"] != r2.json()["id"]


# ═════════════════════════════════════════════════════════════════
# 标签列表
# ═════════════════════════════════════════════════════════════════

class TestListTags:
    """list — GET /api/tags/ 返回当前用户所有标签含使用计数。"""

    def test_list_tags(self, client, auth_headers):
        """创建多个标签后列表应包含它们。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()
        client.post(f"{NOTES}{note['id']}/tags", json={"name": "a"}, headers=auth_headers)
        client.post(f"{NOTES}{note['id']}/tags", json={"name": "b"}, headers=auth_headers)
        client.post(f"{NOTES}{note['id']}/tags", json={"name": "c"}, headers=auth_headers)

        resp = client.get(TAGS, headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 3
        names = sorted(t["name"] for t in items)
        assert names == ["a", "b", "c"]

    def test_list_tags_with_note_count(self, client, auth_headers):
        """每个标签应包含 note_count 使用计数。"""
        n1 = client.post(NOTES, json={"title": "N1"}, headers=auth_headers).json()
        n2 = client.post(NOTES, json={"title": "N2"}, headers=auth_headers).json()

        r = client.post(
            f"{NOTES}{n1['id']}/tags",
            json={"name": "shared"},
            headers=auth_headers,
        )
        tag_id = r.json()["id"]
        client.post(
            f"{NOTES}{n2['id']}/tags",
            json={"name": "shared"},
            headers=auth_headers,
        )

        resp = client.get(TAGS, headers=auth_headers)
        tag = next(t for t in resp.json()["items"] if t["id"] == tag_id)
        assert tag["note_count"] == 2  # 两个笔记都用了这个标签

    def test_list_empty(self, client, auth_headers):
        """新用户无标签 → 空列表。"""
        resp = client.get(TAGS, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []


# ═════════════════════════════════════════════════════════════════
# 标签删除（从笔记移除关联）
# ═════════════════════════════════════════════════════════════════

class TestDeleteTag:
    """delete — DELETE /api/notes/{note_id}/tags/{tag_id} 移除标签关联。"""

    def test_delete_tag(self, client, auth_headers):
        """从笔记移除标签关联 → 204。"""
        note = client.post(NOTES, json={"title": "N"}, headers=auth_headers).json()
        r = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "temp"},
            headers=auth_headers,
        )
        tag_id = r.json()["id"]

        resp = client.delete(
            f"{NOTES}{note['id']}/tags/{tag_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # 移除后 note_count 应减少
        list_resp = client.get(TAGS, headers=auth_headers)
        tag = next((t for t in list_resp.json()["items"] if t["id"] == tag_id), None)
        assert tag is None or tag["note_count"] == 0


# ═════════════════════════════════════════════════════════════════
# 所有权检查
# ═════════════════════════════════════════════════════════════════

class TestTagNotOwner:
    """not_owner — 非所有者不能操作他人笔记的标签。"""

    def test_add_tag_not_owner(self, client, auth_headers, auth_headers_other):
        """其他用户不能向我的笔记添加标签 → 403。"""
        note = client.post(NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        resp = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "intruder"},
            headers=auth_headers_other,
        )
        assert resp.status_code == 403

    def test_remove_tag_not_owner(self, client, auth_headers, auth_headers_other):
        """其他用户不能从我的笔记移除标签 → 403。"""
        note = client.post(NOTES, json={"title": "Mine"}, headers=auth_headers).json()
        r = client.post(
            f"{NOTES}{note['id']}/tags",
            json={"name": "mine"},
            headers=auth_headers,
        )
        tag_id = r.json()["id"]

        resp = client.delete(
            f"{NOTES}{note['id']}/tags/{tag_id}",
            headers=auth_headers_other,
        )
        assert resp.status_code == 403
