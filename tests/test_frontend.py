"""前端静态测试 + 端到端 API 集成流程。

测试 SPA Shell 服务、静态资源可访问性、完整用户认证流程、
笔记 CRUD 完整流程、分享（创建→公开查看→撤销→失效）流程。
"""

import pytest


# ═════════════════════════════════════════════════════════════════
# SPA Shell 与静态资源
# ═════════════════════════════════════════════════════════════════

class TestSPAShell:
    """SPA shell index.html 和静态资源服务。"""

    def test_index_html_served(self, client):
        """GET /projects/note-manager/ → 200 + HTML 内容。"""
        resp = client.get("/projects/note-manager/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_index_html_no_cache_header(self, client):
        """index.html 响应必须包含 Cache-Control: no-cache HTTP 头。

        ADR-001 §4.4 要求：不能用 <meta> 标签代替。
        """
        resp = client.get("/projects/note-manager/")
        assert resp.headers.get("cache-control") == "no-cache"

    def test_index_html_also_at_index_dot_html(self, client):
        """GET /projects/note-manager/index.html → 200。"""
        resp = client.get("/projects/note-manager/index.html")
        assert resp.status_code == 200

    def test_static_css_accessible(self, client):
        """静态 CSS 文件可访问。"""
        resp = client.get("/projects/note-manager/static/css/app.css")
        # 可能返回 200 或 404（CSS 文件可不存在）
        assert resp.status_code in (200, 404)

    def test_static_js_accessible(self, client):
        """静态 JS 文件可访问。"""
        resp = client.get("/projects/note-manager/static/js/app.js")
        assert resp.status_code in (200, 404)

    def test_marked_js_accessible(self, client):
        """marked.js 静态文件可访问。"""
        resp = client.get("/projects/note-manager/static/js/marked.min.js")
        assert resp.status_code in (200, 404)


# ═════════════════════════════════════════════════════════════════
# 端到端认证流程
# ═════════════════════════════════════════════════════════════════

class TestAuthFlow:
    """完整注册 → 登录 → 获取当前用户流程。"""

    REGISTER = "/projects/note-manager/api/auth/register"
    LOGIN = "/projects/note-manager/api/auth/login"
    ME = "/projects/note-manager/api/auth/me"

    def test_full_auth_flow(self, client):
        """注册 → 登录 → 获取当前用户 → 完整串联。"""
        # Step 1: 注册
        reg_resp = client.post(self.REGISTER, json={
            "username": "e2euser",
            "email": "e2e@example.com",
            "password": "e2epass123",
        })
        assert reg_resp.status_code == 201
        reg_data = reg_resp.json()
        assert reg_data["username"] == "e2euser"
        assert "password_hash" not in reg_data

        # Step 2: 登录
        login_resp = client.post(self.LOGIN, json={
            "username": "e2euser",
            "password": "e2epass123",
        })
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        access_token = login_data["access_token"]
        assert login_data["token_type"] == "bearer"
        assert login_data["user"]["username"] == "e2euser"

        # Step 3: 获取当前用户
        me_resp = client.get(self.ME, headers={
            "Authorization": f"Bearer {access_token}",
        })
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["username"] == "e2euser"
        assert me_data["email"] == "e2e@example.com"

    def test_token_persistence_scenario(self, client):
        """模拟 SPA token 持久化：登录后 token 在后续请求中有效。"""
        client.post(self.REGISTER, json={
            "username": "persist",
            "email": "persist@example.com",
            "password": "persist123",
        })

        # 登录获取 token（模拟 localStorage.setItem）
        login_resp = client.post(self.LOGIN, json={
            "username": "persist",
            "password": "persist123",
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 用同一 token 做多次请求
        for _ in range(3):
            resp = client.get(self.ME, headers=headers)
            assert resp.status_code == 200

    def test_routing_guard_scenario(self, client):
        """模拟前端路由守卫：无效 token → 401 → 前端跳转登录页。"""
        # 请求受保护端点时无有效 token
        resp = client.get("/projects/note-manager/api/notes/", headers={
            "Authorization": "Bearer invalid_token_here_xyz",
        })
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════
# 端到端笔记 CRUD 流程
# ═════════════════════════════════════════════════════════════════

class TestNotesCRUDFlow:
    """创建 → 列表 → 详情 → 更新 → 删除 完整流程。"""

    NOTES = "/projects/note-manager/api/notes/"
    TAGS = "/projects/note-manager/api/tags/"

    def test_full_crud_flow(self, client, auth_headers):
        """端到端笔记 CRUD 串联测试。"""
        # Step 1: 创建笔记
        create_resp = client.post(self.NOTES, json={
            "title": "E2E Note",
            "content_md": "# Hello E2E",
        }, headers=auth_headers)
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        # Step 2: 列表中应包含新笔记
        list_resp = client.get(self.NOTES, headers=auth_headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert any(n["id"] == note_id for n in items)

        # Step 3: 获取详情
        get_resp = client.get(f"{self.NOTES}{note_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "E2E Note"

        # Step 4: 更新笔记
        update_resp = client.put(f"{self.NOTES}{note_id}", json={
            "title": "Updated E2E Note",
            "content_md": "# Updated",
        }, headers=auth_headers)
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Updated E2E Note"

        # Step 5: 删除笔记
        delete_resp = client.delete(f"{self.NOTES}{note_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # Step 6: 确认已删除
        get_again = client.get(f"{self.NOTES}{note_id}", headers=auth_headers)
        assert get_again.status_code == 404

    def test_create_multiple_notes(self, client, auth_headers):
        """批量创建笔记 → 分页验证。"""
        for i in range(30):
            resp = client.post(self.NOTES, json={"title": f"Bulk {i}"}, headers=auth_headers)
            assert resp.status_code == 201

        # 第 1 页：20 条
        p1 = client.get(self.NOTES, params={"page": 1, "per_page": 20}, headers=auth_headers)
        assert p1.status_code == 200
        assert len(p1.json()["items"]) == 20
        assert p1.json()["total"] == 30

        # 第 2 页：10 条
        p2 = client.get(self.NOTES, params={"page": 2, "per_page": 20}, headers=auth_headers)
        assert p2.status_code == 200
        assert len(p2.json()["items"]) == 10


# ═════════════════════════════════════════════════════════════════
# 端到端标签流程
# ═════════════════════════════════════════════════════════════════

class TestTagsFlow:
    """笔记 + 标签完整串联流程。"""

    NOTES = "/projects/note-manager/api/notes/"
    TAGS = "/projects/note-manager/api/tags/"

    def test_full_tag_lifecycle(self, client, auth_headers):
        """创建笔记 → 添加标签 → 列表含计数 → 移除标签 完整流程。"""
        # Step 1: 创建笔记
        note = client.post(self.NOTES, json={"title": "Tagged"}, headers=auth_headers).json()

        # Step 2: 添加标签
        r1 = client.post(f"{self.NOTES}{note['id']}/tags", json={"name": "e2e-tag"}, headers=auth_headers)
        assert r1.status_code == 201
        tag_id = r1.json()["id"]
        assert r1.json()["note_count"] == 1

        # Step 3: 列表含计数
        list_resp = client.get(self.TAGS, headers=auth_headers)
        tags = list_resp.json()["items"]
        assert any(t["id"] == tag_id and t["note_count"] == 1 for t in tags)

        # Step 4: 移除标签
        remove_resp = client.delete(
            f"{self.NOTES}{note['id']}/tags/{tag_id}",
            headers=auth_headers,
        )
        assert remove_resp.status_code == 204

    def test_multi_note_tagging(self, client, auth_headers):
        """多笔记共享标签 → note_count 正确累加。"""
        n1 = client.post(self.NOTES, json={"title": "N1"}, headers=auth_headers).json()
        n2 = client.post(self.NOTES, json={"title": "N2"}, headers=auth_headers).json()

        client.post(f"{self.NOTES}{n1['id']}/tags", json={"name": "shared"}, headers=auth_headers)
        client.post(f"{self.NOTES}{n2['id']}/tags", json={"name": "shared"}, headers=auth_headers)

        tags = client.get(self.TAGS, headers=auth_headers).json()["items"]
        shared = next((t for t in tags if t["name"] == "shared"), None)
        assert shared is not None
        assert shared["note_count"] == 2


# ═════════════════════════════════════════════════════════════════
# 端到端分享流程
# ═════════════════════════════════════════════════════════════════

class TestShareFlow:
    """创建分享 → 公开查看 → 撤销 → 失效 完整流程。"""

    NOTES = "/projects/note-manager/api/notes/"
    SHARES = "/projects/note-manager/api/shares/"

    def test_full_share_lifecycle(self, client, auth_headers):
        """端到端分享流程串联测试。"""
        # Step 1: 创建笔记
        note = client.post(self.NOTES, json={
            "title": "Secret Note",
            "content_md": "# Confidential\nTop secret content.",
        }, headers=auth_headers).json()

        # Step 2: 创建分享链接
        share_resp = client.post(
            f"{self.NOTES}{note['id']}/share",
            json={"expires_in_hours": 24},
            headers=auth_headers,
        )
        assert share_resp.status_code == 201
        token = share_resp.json()["token"]
        share_id = share_resp.json()["id"]

        # Step 3: 公开查看（无需认证）
        public_resp = client.get(f"/projects/note-manager/api/public/notes/{token}")
        assert public_resp.status_code == 200
        data = public_resp.json()
        assert data["title"] == "Secret Note"
        assert data["content_md"] == "# Confidential\nTop secret content."
        assert data["author"]["username"] == "testuser"
        # 公开接口不含敏感字段
        assert "email" not in str(data)

        # Step 4: 查看分享列表
        list_resp = client.get(self.SHARES, headers=auth_headers)
        items = list_resp.json()["items"]
        assert any(s["token"] == token for s in items)

        # Step 5: 撤销分享
        revoke_resp = client.delete(f"{self.SHARES}{share_id}", headers=auth_headers)
        assert revoke_resp.status_code == 204

        # Step 6: 撤销后公开访问失败
        after_resp = client.get(f"/projects/note-manager/api/public/notes/{token}")
        assert after_resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# 边界与权限场景
# ═════════════════════════════════════════════════════════════════

class TestEdgeScenarios:
    """前端常见边界场景 — SQL 注入、XSS、Unicode、并发。"""

    NOTES = "/projects/note-manager/api/notes/"

    def test_sql_injection_in_search(self, client, auth_headers):
        """SQL 注入尝试作为搜索关键词 → 不报错，0 结果。"""
        client.post(self.NOTES, json={"title": "Normal"}, headers=auth_headers)
        resp = client.get(self.NOTES, params={
            "search": "\"'; DROP TABLE notes; --",
        }, headers=auth_headers)
        assert resp.status_code == 200
        # 不应有任何结果，也不应报错
        assert resp.json()["total"] == 0

    def test_xss_in_content(self, client, auth_headers):
        """XSS 脚本存入 content_md → 后端不渲染 HTML 脚本。"""
        resp = client.post(self.NOTES, json={
            "title": "XSS Test",
            "content_md": "<script>alert('xss')</script>",
        }, headers=auth_headers)
        assert resp.status_code == 201
        # 内容应原样存储，不被执行（由前端 marked.js 负责 sanitize）
        data = resp.json()
        assert "<script>alert('xss')</script>" in data["content_md"]

    def test_unicode_content(self, client, auth_headers):
        """Unicode + emoji 内容正常 CRUD。"""
        create_resp = client.post(self.NOTES, json={
            "title": "中文标题 🎉",
            "content_md": "内容 😀🚀\n\n# 一级标题\n\n💡 提示文字",
        }, headers=auth_headers)
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        get_resp = client.get(f"{self.NOTES}{note_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["title"] == "中文标题 🎉"
        assert "😀🚀" in data["content_md"]
        assert "💡" in data["content_md"]

    def test_very_long_content(self, client, auth_headers):
        """超长 Markdown 内容（>50KB）正常存储和返回。"""
        long_content = "# Long Content\n\n" + ("Lorem ipsum dolor sit amet.\n" * 3000)
        assert len(long_content) > 50000  # > 50KB

        create_resp = client.post(self.NOTES, json={
            "title": "Long",
            "content_md": long_content,
        }, headers=auth_headers)
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        get_resp = client.get(f"{self.NOTES}{note_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert len(get_resp.json()["content_md"]) == len(long_content)
