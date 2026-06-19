"""笔记 CRUD API 集成测试 — 创建/列表/分页/搜索/更新/删除/所有权检查。

使用 FastAPI TestClient + dependency_override（通过 conftest.py 的 ``client`` fixture）。
全部端点需要 JWT 认证（通过 ``auth_headers`` fixture）。
"""

import pytest


# ═════════════════════════════════════════════════════════════════
# POST / — 创建笔记
# ═════════════════════════════════════════════════════════════════

class TestCreateNote:
    """POST /api/notes/"""

    API = "/projects/note-manager/api/notes/"

    def test_create_with_title_and_content(self, client, auth_headers):
        """创建带标题和正文的笔记 → 201。"""
        resp = client.post(self.API, json={
            "title": "My Note",
            "content_md": "# Hello\nWorld",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Note"
        assert data["content_md"] == "# Hello\nWorld"
        assert data["id"] is not None
        assert data["tags"] == []
        assert data["created_at"] is not None

    def test_create_default_title(self, client, auth_headers):
        """不传 title → 默认 "Untitled"。"""
        resp = client.post(self.API, json={}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "Untitled"

    def test_create_with_tags(self, client, auth_headers):
        """创建笔记并附带标签 ID 列表。"""
        # 先通过向笔记添加标签来创建标签
        note_temp = client.post(self.API, json={"title": "Temp"}, headers=auth_headers).json()
        resp_tag = client.post(
            f"{self.API}{note_temp['id']}/tags",
            json={"name": "test-tag"},
            headers=auth_headers,
        )
        tag_id = resp_tag.json()["id"]

        resp = client.post(self.API, json={
            "title": "Tagged Note",
            "tag_ids": [tag_id],
        }, headers=auth_headers)
        assert resp.status_code == 201
        tags = resp.json()["tags"]
        assert len(tags) == 1
        assert tags[0]["name"] == "test-tag"

    def test_create_unauthorized(self, client):
        """无 token → 401。"""
        resp = client.post(self.API, json={"title": "No"})
        assert resp.status_code == 401

    def test_create_title_too_long(self, client, auth_headers):
        """标题 > 256 字符 → 422。"""
        resp = client.post(self.API, json={
            "title": "x" * 257,
        }, headers=auth_headers)
        assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════
# GET / — 分页列表
# ═════════════════════════════════════════════════════════════════

class TestListNotes:
    """GET /api/notes/?page=&per_page=&search=&tag="""

    API = "/projects/note-manager/api/notes/"

    def test_list_empty(self, client, auth_headers):
        """新用户无笔记 → 空列表。"""
        resp = client.get(self.API, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["per_page"] == 20

    def test_list_with_items(self, client, auth_headers):
        """创建笔记后列表应包含它们。"""
        for i in range(3):
            client.post(self.API, json={"title": f"Note {i}"}, headers=auth_headers)

        resp = client.get(self.API, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_pagination_page_2(self, client, auth_headers):
        """分页 — 第 2 页返回剩余条目。"""
        for i in range(25):
            client.post(self.API, json={"title": f"Note {i}"}, headers=auth_headers)

        resp = client.get(self.API, params={"page": 2, "per_page": 20}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["per_page"] == 20
        assert len(data["items"]) == 5  # 25 total, page 2 has 5

    def test_search_by_title(self, client, auth_headers):
        """搜索 — 按标题关键词过滤。"""
        client.post(self.API, json={"title": "Python Guide"}, headers=auth_headers)
        client.post(self.API, json={"title": "JavaScript Guide"}, headers=auth_headers)
        client.post(self.API, json={"title": "SQL Notes"}, headers=auth_headers)

        resp = client.get(self.API, params={"search": "python"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Python Guide"

    def test_search_by_content(self, client, auth_headers):
        """搜索 — 按正文关键词过滤。"""
        client.post(self.API, json={"title": "Note A", "content_md": "learn python"}, headers=auth_headers)
        client.post(self.API, json={"title": "Note B", "content_md": "learn rust"}, headers=auth_headers)

        resp = client.get(self.API, params={"search": "python"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_search_case_insensitive(self, client, auth_headers):
        """搜索 — 大小写不敏感（ILIKE）。"""
        client.post(self.API, json={"title": "PYTHON"}, headers=auth_headers)
        resp = client.get(self.API, params={"search": "python"}, headers=auth_headers)
        assert resp.json()["total"] == 1

    def test_tag_filter(self, client, auth_headers):
        """标签筛选 — 按单个标签过滤。"""
        # 直接在目标笔记上创建标签（避免污染搜索结果）
        n1 = client.post(self.API, json={"title": "Work Note"}, headers=auth_headers).json()
        n2 = client.post(self.API, json={"title": "Personal Note"}, headers=auth_headers).json()

        t1 = client.post(f"{self.API}{n1['id']}/tags", json={"name": "work"}, headers=auth_headers).json()
        t2 = client.post(f"{self.API}{n2['id']}/tags", json={"name": "personal"}, headers=auth_headers).json()

        resp = client.get(self.API, params={"tag": "work"}, headers=auth_headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "Work Note"

    def test_tag_filter_and_logic(self, client, auth_headers):
        """标签筛选 — AND 逻辑（多标签逗号分隔）。"""
        # 直接在目标笔记上创建标签
        n1 = client.post(self.API, json={"title": "Full Stack"}, headers=auth_headers).json()
        n2 = client.post(self.API, json={"title": "Python Only"}, headers=auth_headers).json()

        # 为 Full Stack 添加 python 和 web 两个标签
        t1 = client.post(f"{self.API}{n1['id']}/tags", json={"name": "python"}, headers=auth_headers).json()
        t2 = client.post(f"{self.API}{n1['id']}/tags", json={"name": "web"}, headers=auth_headers).json()
        # 为 Python Only 只添加 python 标签（复用已创建的标签）
        client.post(f"{self.API}{n2['id']}/tags", json={"name": "python"}, headers=auth_headers)

        resp = client.get(self.API, params={"tag": "python,web"}, headers=auth_headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "Full Stack"

    def test_tag_filter_nonexistent(self, client, auth_headers):
        """标签筛选 — 不存在的标签返回空。"""
        client.post(self.API, json={"title": "Note"}, headers=auth_headers)
        resp = client.get(self.API, params={"tag": "nonexistent"}, headers=auth_headers)
        assert resp.json()["total"] == 0

    def test_per_page_limit(self, client, auth_headers):
        """per_page 上限为 100。"""
        resp = client.get(self.API, params={"per_page": 200}, headers=auth_headers)
        assert resp.status_code == 422  # 超过上限被拒绝


# ═════════════════════════════════════════════════════════════════
# GET /{id} — 笔记详情
# ═════════════════════════════════════════════════════════════════

class TestGetNote:
    """GET /api/notes/{id}"""

    API = "/projects/note-manager/api/notes/"

    def test_get_note(self, client, auth_headers):
        """获取自己的笔记 → 200 + 完整数据。"""
        create_resp = client.post(self.API, json={
            "title": "Detail", "content_md": "Content",
        }, headers=auth_headers)
        note_id = create_resp.json()["id"]

        resp = client.get(f"{self.API}{note_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail"
        assert data["content_md"] == "Content"

    def test_get_not_found(self, client, auth_headers):
        """不存在的笔记 → 404。"""
        resp = client.get(f"{self.API}99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_not_owner(self, client, auth_headers, auth_headers_other):
        """其他用户的笔记 → 404（安全遮罩）。"""
        # user A 创建笔记
        create_resp = client.post(self.API, json={"title": "A's"}, headers=auth_headers)
        note_id = create_resp.json()["id"]

        # user B 尝试查看
        resp = client.get(f"{self.API}{note_id}", headers=auth_headers_other)
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# PUT /{id} — 更新笔记
# ═════════════════════════════════════════════════════════════════

class TestUpdateNote:
    """PUT /api/notes/{id}"""

    API = "/projects/note-manager/api/notes/"

    def test_update_title(self, client, auth_headers):
        """更新标题 → 200。"""
        create_resp = client.post(self.API, json={"title": "Old"}, headers=auth_headers)
        note_id = create_resp.json()["id"]

        resp = client.put(f"{self.API}{note_id}", json={"title": "New Title"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"
        assert resp.json()["content_md"] == ""  # 未修改

    def test_update_content(self, client, auth_headers):
        """更新正文 → 200。"""
        create_resp = client.post(self.API, json={"title": "T"}, headers=auth_headers)
        note_id = create_resp.json()["id"]

        resp = client.put(f"{self.API}{note_id}", json={"content_md": "Updated"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["content_md"] == "Updated"

    def test_update_tags(self, client, auth_headers):
        """更新标签关联 → 200。"""
        note_temp = client.post(self.API, json={"title": "Temp"}, headers=auth_headers).json()
        t1 = client.post(f"{self.API}{note_temp['id']}/tags", json={"name": "red"}, headers=auth_headers).json()
        t2 = client.post(f"{self.API}{note_temp['id']}/tags", json={"name": "blue"}, headers=auth_headers).json()

        create_resp = client.post(self.API, json={
            "title": "Colored", "tag_ids": [t1["id"]],
        }, headers=auth_headers)
        note_id = create_resp.json()["id"]

        # 替换标签为 [t2]
        resp = client.put(f"{self.API}{note_id}", json={"tag_ids": [t2["id"]]}, headers=auth_headers)
        assert resp.status_code == 200
        tags = resp.json()["tags"]
        assert len(tags) == 1
        assert tags[0]["name"] == "blue"

    def test_update_not_owner(self, client, auth_headers, auth_headers_other):
        """非所有者更新 → 403。"""
        create_resp = client.post(self.API, json={"title": "Mine"}, headers=auth_headers)
        note_id = create_resp.json()["id"]

        resp = client.put(f"{self.API}{note_id}", json={"title": "Hacked"}, headers=auth_headers_other)
        assert resp.status_code == 403

    def test_update_not_found(self, client, auth_headers):
        """更新不存在的笔记 → 404。"""
        resp = client.put(f"{self.API}99999", json={"title": "Ghost"}, headers=auth_headers)
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# DELETE /{id} — 删除笔记
# ═════════════════════════════════════════════════════════════════

class TestDeleteNote:
    """DELETE /api/notes/{id}"""

    API = "/projects/note-manager/api/notes/"

    def test_delete_note(self, client, auth_headers):
        """删除自己的笔记 → 204。"""
        create_resp = client.post(self.API, json={"title": "Delete Me"}, headers=auth_headers)
        note_id = create_resp.json()["id"]

        resp = client.delete(f"{self.API}{note_id}", headers=auth_headers)
        assert resp.status_code == 204

        # 确认已删除
        get_resp = client.get(f"{self.API}{note_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_not_owner(self, client, auth_headers, auth_headers_other):
        """非所有者删除 → 403。"""
        create_resp = client.post(self.API, json={"title": "Mine"}, headers=auth_headers)
        note_id = create_resp.json()["id"]

        resp = client.delete(f"{self.API}{note_id}", headers=auth_headers_other)
        assert resp.status_code == 403

    def test_delete_not_found(self, client, auth_headers):
        """删除不存在的笔记 → 404。"""
        resp = client.delete(f"{self.API}99999", headers=auth_headers)
        assert resp.status_code == 404
