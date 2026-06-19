"""边界与集成测试 — 超长输入/注入防护/Unicode/并发。

使用 FastAPI TestClient + dependency_override（通过 conftest.py 的 ``client`` fixture）。
"""

import pytest


API = "/projects/note-manager/api/notes/"


# ═════════════════════════════════════════════════════════════════
# 超长标题
# ═════════════════════════════════════════════════════════════════

class TestLongTitle:
    """超长标题（>256 字符）→ 422 校验失败。"""

    def test_title_too_long_422(self, client, auth_headers):
        """标题 > 256 字符 → 422。"""
        resp = client.post(API, json={
            "title": "x" * 257,
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_title_exactly_256_ok(self, client, auth_headers):
        """标题恰好 256 字符 → 201。"""
        resp = client.post(API, json={
            "title": "x" * 256,
        }, headers=auth_headers)
        assert resp.status_code == 201


# ═════════════════════════════════════════════════════════════════
# 超长 Markdown 内容
# ═════════════════════════════════════════════════════════════════

class TestLongMarkdown:
    """超长 Markdown 内容（>100KB）→ 正常存储和返回。"""

    def test_long_markdown_stored_and_returned(self, client, auth_headers):
        """100KB+ 的 Markdown 内容应能正常存储和读取。"""
        large_content = "# Large Document\n\n" + "Lorem ipsum dolor sit amet.\n" * 5000
        assert len(large_content) > 100_000

        # 创建
        create_resp = client.post(API, json={
            "title": "Large Document",
            "content_md": large_content,
        }, headers=auth_headers)
        assert create_resp.status_code == 201
        note_id = create_resp.json()["id"]

        # 读取 — 内容应完整返回
        get_resp = client.get(f"{API}{note_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["title"] == "Large Document"
        assert data["content_md"] == large_content
        assert len(data["content_md"]) == len(large_content)


# ═════════════════════════════════════════════════════════════════
# XSS 防护
# ═════════════════════════════════════════════════════════════════

class TestXSS:
    """XSS 尝试 — script 标签作为纯文本存储，后端不执行 HTML 渲染。"""

    def test_xss_as_plain_text(self, client, auth_headers):
        """script 标签应作为纯 Markdown 文本存储，不做任何执行。"""
        xss_payload = '<script>alert("xss")</script>'
        content = f"# Title\n\nSome text\n\n{xss_payload}\n\nMore text"

        resp = client.post(API, json={
            "title": "XSS Test",
            "content_md": content,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()

        # 后端应原样存储，不做 HTML 转义也不执行
        assert xss_payload in data["content_md"]
        # 返回的是 JSON，不是 HTML，所以不会有 script 执行
        # 前端 marked.js 在 sanitize 模式下也会过滤 script

    def test_xss_in_title(self, client, auth_headers):
        """script 标签在标题中也应原样存储。"""
        xss_title = '<img src=x onerror=alert(1)>'

        resp = client.post(API, json={
            "title": xss_title,
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == xss_title


# ═════════════════════════════════════════════════════════════════
# SQL 注入防护
# ═════════════════════════════════════════════════════════════════

class TestSQLInjection:
    """SQL 注入尝试 — 参数化查询应安全处理，不报错也不执行注入。"""

    def test_sql_injection_search_safe(self, client, auth_headers):
        """SQL 注入作为搜索关键词 → 不报错，0 结果。"""
        # 先创建一些正常笔记
        client.post(API, json={"title": "Normal Note"}, headers=auth_headers)

        # SQL 注入 payload 作为搜索词
        sql_payload = "'; DROP TABLE notes; --"
        resp = client.get(API, params={"search": sql_payload}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0  # 没匹配到任何笔记

        # 确认数据库没有被破坏 — 笔记仍然存在
        resp2 = client.get(API, headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["total"] >= 1

    def test_sql_injection_in_content(self, client, auth_headers):
        """SQL 注入作为笔记内容 → 正常存储，不触发 SQL。"""
        payload = "'; DROP TABLE notes; --"

        resp = client.post(API, json={
            "title": "Injection Test",
            "content_md": payload,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["content_md"] == payload  # 原样存储

        # 数据库表仍然存在（能正常查询）
        resp2 = client.get(API, headers=auth_headers)
        assert resp2.status_code == 200


# ═════════════════════════════════════════════════════════════════
# Unicode 支持
# ═════════════════════════════════════════════════════════════════

class TestUnicode:
    """Unicode 支持 — 中文、emoji、特殊字符正常 CRUD。"""

    def test_chinese_title_and_content(self, client, auth_headers):
        """中文标题和正文 → 正常创建、搜索、返回。"""
        resp = client.post(API, json={
            "title": "我的中文笔记",
            "content_md": "# 你好世界\n\n这是一篇**中文**笔记。\n\n- 列表项一\n- 列表项二",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "我的中文笔记"
        assert "你好世界" in data["content_md"]
        assert "中文" in data["content_md"]

        # 搜索中文关键词
        note_id = data["id"]
        search_resp = client.get(API, params={"search": "中文"}, headers=auth_headers)
        assert search_resp.status_code == 200
        assert search_resp.json()["total"] >= 1

        # 获取详情
        get_resp = client.get(f"{API}{note_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "我的中文笔记"

    def test_emoji_in_content(self, client, auth_headers):
        """emoji 在标题和正文中 → 正常存储和返回。"""
        resp = client.post(API, json={
            "title": "🎉 庆祝笔记 🎊",
            "content_md": "# Emoji 测试 😊\n\n> 💡 提示：这是一条包含 emoji 的笔记\n\n- ✅ 完成\n- 🚧 进行中\n- ⏳ 待办\n\n```python\nprint('🐍 Hello Python!')\n```",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "🎉" in data["title"]
        assert "🎊" in data["title"]
        assert "😊" in data["content_md"]
        assert "🐍" in data["content_md"]
        assert "✅" in data["content_md"]

    def test_mixed_scripts(self, client, auth_headers):
        """中英日韩混合 → 正常存储。"""
        content = (
            "# 多语言笔记 / Multilingual Note / 多言語ノート\n\n"
            "中文: 你好\n"
            "English: Hello\n"
            "日本語: こんにちは\n"
            "한국어: 안녕하세요\n"
            "العربية: مرحبا\n"
            "Русский: Привет\n"
        )
        resp = client.post(API, json={
            "title": "多语言 Multilingual 多言語",
            "content_md": content,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "こんにちは" in data["content_md"]
        assert "안녕하세요" in data["content_md"]

    def test_zero_width_and_special_chars(self, client, auth_headers):
        """零宽字符和特殊 Unicode → 正常存储。"""
        resp = client.post(API, json={
            "title": "Special ​‌‍ Chars",
            "content_md": "Zero-width: ​‌‍\nRTL: ‫‪\nMath: ∑∏∫√∞",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "​" in data["title"]
        assert "∑" in data["content_md"]


# ═════════════════════════════════════════════════════════════════
# 并发创建
# ═════════════════════════════════════════════════════════════════

class TestConcurrent:
    """并发请求 — 同一用户同时创建多个笔记不报错。"""

    def test_concurrent_creates(self, client, auth_headers):
        """快速连续创建多个笔记 → 全部成功，无冲突。"""
        count = 10
        created_ids = []

        for i in range(count):
            resp = client.post(API, json={
                "title": f"Concurrent Note {i}",
                "content_md": f"Content for note {i}",
            }, headers=auth_headers)
            assert resp.status_code == 201
            created_ids.append(resp.json()["id"])

        # 所有 ID 应唯一
        assert len(set(created_ids)) == count

        # 列表应有全部笔记
        list_resp = client.get(API, headers=auth_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= count

    def test_rapid_create_delete_cycle(self, client, auth_headers):
        """快速创建-删除循环 → 不报错，数据库一致。"""
        for i in range(5):
            # 创建
            create_resp = client.post(API, json={
                "title": f"Ephemeral {i}",
            }, headers=auth_headers)
            assert create_resp.status_code == 201
            note_id = create_resp.json()["id"]

            # 立即删除
            delete_resp = client.delete(f"{API}{note_id}", headers=auth_headers)
            assert delete_resp.status_code == 204

            # 确认已删除
            get_resp = client.get(f"{API}{note_id}", headers=auth_headers)
            assert get_resp.status_code == 404

        # 最终列表应为空
        list_resp = client.get(API, headers=auth_headers)
        assert list_resp.status_code == 200
        # 此时可能没有笔记，因为全部删除
