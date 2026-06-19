"""演示数据种子 — 首次启动时通过 SEED_DEMO=true 触发。

幂等：检查演示用户是否已存在，存在则跳过。
"""

import bcrypt
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from .config import settings
from .models import User, Note, Tag, NoteTag, ShareLink


# ═══════════════════════════════════════════════════════════════
# 演示用户定义
# ═══════════════════════════════════════════════════════════════

_DEMO_USERS = [
    {
        "username": "demo",
        "email": "demo@example.com",
        "password": "demo123",
        "is_demo": True,
        "tags": ["工作", "个人", "学习"],
        "notes": [
            {
                "title": "欢迎使用笔记管理系统",
                "content_md": (
                    "# 🎉 欢迎\n\n"
                    "这是你的第一笔记！你可以在这里用 **Markdown** 记录任何内容。\n\n"
                    "## 功能一览\n\n"
                    "- 📝 **撰写笔记** — 支持 Markdown 实时预览\n"
                    "- 🔖 **标签管理** — 为笔记添加标签方便分类\n"
                    "- 🔗 **分享链接** — 生成只读分享链接给朋友\n"
                    "- 🔒 **账户安全** — bcrypt 密码加密 + JWT 鉴权\n\n"
                    "> 小提示：按 `Ctrl+S` 快速保存笔记。"
                ),
                "tag_names": ["工作"],
            },
            {
                "title": "Markdown 语法速查",
                "content_md": (
                    "# Markdown 快速参考\n\n"
                    "## 标题\n"
                    "```markdown\n"
                    "# H1\n"
                    "## H2\n"
                    "### H3\n"
                    "```\n\n"
                    "## 强调\n"
                    "- **粗体** `**text**`\n"
                    "- *斜体* `*text*`\n"
                    "- ~~删除线~~ `~~text~~`\n\n"
                    "## 列表\n"
                    "1. 有序项\n"
                    "2. 第二项\n\n"
                    "- 无序项\n"
                    "- 另一项\n\n"
                    "## 代码块\n"
                    "```python\n"
                    "def hello():\n"
                    '    print("Hello, World!")\n'
                    "```\n\n"
                    "## 链接与图片\n"
                    '[链接](https://example.com)\n\n'
                    "## 引用\n"
                    "> 这是一段引用文字。\n\n"
                    "## 表格\n"
                    "| 特性 | 支持 |\n"
                    "|------|------|\n"
                    "| 标题 | ✅ |\n"
                    "| 列表 | ✅ |\n"
                    "| 代码 | ✅ |\n"
                ),
                "tag_names": ["学习"],
            },
            {
                "title": "本周工作计划",
                "content_md": (
                    "# 📋 本周工作计划 (Week 25)\n\n"
                    "## 周一\n"
                    "- [x] 团队站会\n"
                    "- [x] 完成 API 设计文档\n"
                    "- [ ] Code Review PR #42\n\n"
                    "## 周二\n"
                    "- [ ] 实现用户认证模块\n"
                    "- [ ] 编写单元测试\n\n"
                    "## 周三\n"
                    "- [ ] 前端页面联调\n"
                    "- [ ] 性能优化\n\n"
                    "## 周四\n"
                    "- [ ] 集成测试\n"
                    "- [ ] 修复 Bug\n\n"
                    "## 周五\n"
                    "- [ ] 周报总结\n"
                    "- [ ] 下周计划\n\n"
                    "> **优先级**: 认证模块 > 前端联调 > 测试"
                ),
                "tag_names": ["工作"],
            },
            {
                "title": "Python 学习笔记",
                "content_md": (
                    "# 🐍 Python 学习笔记\n\n"
                    "## 装饰器 (Decorator)\n\n"
                    "```python\n"
                    "from functools import wraps\n\n"
                    "def timer(func):\n"
                    "    @wraps(func)\n"
                    "    def wrapper(*args, **kwargs):\n"
                    "        import time\n"
                    "        start = time.time()\n"
                    "        result = func(*args, **kwargs)\n"
                    '        print(f"{func.__name__} took {time.time() - start:.2f}s")\n'
                    "        return result\n"
                    "    return wrapper\n"
                    "```\n\n"
                    "## 列表推导式\n\n"
                    "```python\n"
                    "# 基础形式\n"
                    "squares = [x**2 for x in range(10)]\n\n"
                    "# 带条件\n"
                    "evens = [x for x in range(20) if x % 2 == 0]\n\n"
                    "# 嵌套\n"
                    "matrix = [[i*j for j in range(3)] for i in range(3)]\n"
                    "```\n\n"
                    "## 类型注解 (Python 3.10+)\n\n"
                    "```python\n"
                    "def greet(name: str) -> str:\n"
                    '    return f"Hello, {name}!"\n'
                    "```\n\n"
                    "## 常用标准库\n"
                    "- `pathlib` — 路径操作\n"
                    "- `dataclasses` — 数据类\n"
                    "- `itertools` — 迭代工具\n"
                    "- `collections` — 容器类型\n"
                ),
                "tag_names": ["学习", "个人"],
            },
            {
                "title": "好书推荐",
                "content_md": (
                    "# 📚 技术书籍推荐\n\n"
                    "## 软件工程\n\n"
                    "1. **《代码整洁之道》** — Robert C. Martin\n"
                    "   - 写出可读、可维护的代码\n"
                    "   - 必读经典，适合所有级别的开发者\n\n"
                    "2. **《重构》** — Martin Fowler\n"
                    "   - 改善既有代码的设计\n"
                    "   - 大量实战案例\n\n"
                    "3. **《设计模式》** — GoF\n"
                    "   - 23 种经典设计模式\n"
                    "   - 面向对象开发的基石\n\n"
                    "## 思维与效率\n\n"
                    "- **《程序员修炼之道》** — 实用主义者的成长指南\n"
                    "- **《黑客与画家》** — Paul Graham 的经典文集\n"
                    "- **《深度工作》** — 如何在分心世界中专注\n\n"
                    "> 你有什么推荐的书？记下来分享给朋友吧！📖"
                ),
                "tag_names": ["个人"],
            },
        ],
    },
    {
        "username": "alice",
        "email": "alice@example.com",
        "password": "alice123",
        "is_demo": True,
        "tags": ["前端", "设计", "阅读"],
        "notes": [
            {
                "title": "CSS Grid 布局笔记",
                "content_md": (
                    "# CSS Grid 布局\n\n"
                    "## 基础概念\n\n"
                    "```css\n"
                    ".container {\n"
                    "  display: grid;\n"
                    "  grid-template-columns: repeat(3, 1fr);\n"
                    "  gap: 16px;\n"
                    "}\n"
                    "```\n\n"
                    "## Grid vs Flexbox\n\n"
                    "| 场景 | Grid | Flexbox |\n"
                    "|------|------|--------|\n"
                    "| 二维布局 | ✅ | ❌ |\n"
                    "| 一维排列 | ✅ | ✅ |\n"
                    "| 响应式 | ✅ | ✅ |\n\n"
                    "## 常用属性\n"
                    "- `grid-template-areas` — 命名区域\n"
                    "- `fr` 单位 — 按比例分配空间\n"
                    "- `minmax()` — 最小/最大尺寸约束\n"
                    "- `auto-fill` / `auto-fit` — 自动列数\n"
                ),
                "tag_names": ["前端", "设计"],
            },
            {
                "title": "React 组件设计原则",
                "content_md": (
                    "# React 组件设计原则\n\n"
                    "## 单一职责\n"
                    "每个组件只做一件事，做好一件事。\n\n"
                    "## 可组合性\n"
                    "```jsx\n"
                    "function Page() {\n"
                    "  return (\n"
                    "    <Layout>\n"
                    "      <Header />\n"
                    "      <Sidebar />\n"
                    "      <Content />\n"
                    "    </Layout>\n"
                    "  );\n"
                    "}\n"
                    "```\n\n"
                    "## Props 设计\n"
                    "- 保持 Props 扁平\n"
                    "- 避免传递整个对象\n"
                    "- 使用 TypeScript 类型定义\n\n"
                    "## 状态管理\n"
                    "- 状态尽量下沉\n"
                    "- 避免 prop drilling\n"
                    "- Context 用于全局共享\n"
                ),
                "tag_names": ["前端"],
            },
            {
                "title": "设计配色参考",
                "content_md": (
                    "# 🎨 配色方案参考\n\n"
                    "## 现代极简\n"
                    "- 主色：`#2563EB` (Blue)\n"
                    "- 背景：`#FAFAFA`\n"
                    "- 文字：`#1A1A1A`\n\n"
                    "## 温暖自然\n"
                    "- 主色：`#D97706` (Amber)\n"
                    "- 背景：`#FFFBEB`\n"
                    "- 文字：`#422006`\n\n"
                    "## 暗色模式\n"
                    "- 主色：`#818CF8` (Indigo)\n"
                    "- 背景：`#1E1E2E`\n"
                    "- 文字：`#CDD6F4`\n\n"
                    "> 推荐工具：Coolors.co、Adobe Color"
                ),
                "tag_names": ["设计"],
            },
            {
                "title": "读书笔记：《设计中的设计》",
                "content_md": (
                    "# 《设计中的设计》— 原研哉\n\n"
                    "## 核心观点\n\n"
                    "**「白」不是无色，而是包含所有可能的颜色。**\n\n"
                    "## 关键概念\n"
                    "1. **Emptiness (空)** — 留白给予想象空间\n"
                    "2. **Simplicity (简)** — 去除装饰，回归本质\n"
                    "3. **Subtlety (微)** — 微妙之处见功力\n\n"
                    "## 与前端的关系\n"
                    "- 负空间 (Negative Space) = CSS 中的留白\n"
                    "- 信息层级的「白」= 让重要内容突出\n"
                    "- 极简 UI ≠ 简单，是克制的智慧\n\n"
                    "> 「设计不是装饰，而是沟通。」"
                ),
                "tag_names": ["设计", "阅读"],
            },
            {
                "title": "2025 阅读清单",
                "content_md": (
                    "# 📖 2025 阅读清单\n\n"
                    "## 技术\n"
                    "- [x] 《JavaScript 高级程序设计》\n"
                    "- [x] 《CSS 权威指南》\n"
                    "- [ ] 《深入浅出 Node.js》\n"
                    "- [ ] 《Web 性能权威指南》\n\n"
                    "## 设计\n"
                    "- [x] 《写给大家看的设计书》\n"
                    "- [ ] 《Design Systems》\n"
                    "- [ ] 《About Face》\n\n"
                    "## 文学\n"
                    "- [x] 《百年孤独》\n"
                    "- [ ] 《挪威的森林》\n"
                    "- [ ] 《三体》\n\n"
                    "进度：5/10 已完成"
                ),
                "tag_names": ["阅读"],
            },
        ],
    },
    {
        "username": "bob",
        "email": "bob@example.com",
        "password": "bob123",
        "is_demo": True,
        "tags": ["项目", "DevOps", "数据库"],
        "notes": [
            {
                "title": "项目上线检查清单",
                "content_md": (
                    "# 🚀 上线前检查清单\n\n"
                    "## 代码质量\n"
                    "- [ ] 所有测试通过\n"
                    "- [ ] Code Review 完成\n"
                    "- [ ] Lint 零警告\n"
                    "- [ ] 无 console.log / TODO 残留\n\n"
                    "## 安全\n"
                    "- [ ] 依赖无已知漏洞 (`pip audit`)\n"
                    "- [ ] 环境变量已设、.env 不入库\n"
                    "- [ ] API 鉴权正常\n"
                    "- [ ] HTTPS 已配置\n\n"
                    "## 性能\n"
                    "- [ ] 数据库查询已优化\n"
                    "- [ ] 静态资源 CDN / 缓存策略\n"
                    "- [ ] 关键路径 < 2s\n\n"
                    "## 监控\n"
                    "- [ ] 健康检查端点正常\n"
                    "- [ ] 日志聚合就绪\n"
                    "- [ ] 告警规则已配置\n\n"
                    "> 上线前逐项确认，签字后方可执行！"
                ),
                "tag_names": ["项目", "DevOps"],
            },
            {
                "title": "Docker 常用命令",
                "content_md": (
                    "# 🐳 Docker 常用命令\n\n"
                    "## 容器管理\n"
                    "```bash\n"
                    "docker ps -a              # 列出所有容器\n"
                    "docker run -d -p 80:80 nginx  # 后台运行\n"
                    "docker exec -it <id> bash # 进入容器\n"
                    "docker logs -f <id>       # 跟踪日志\n"
                    "```\n\n"
                    "## 镜像管理\n"
                    "```bash\n"
                    "docker images             # 列出镜像\n"
                    "docker build -t app:v1 .  # 构建镜像\n"
                    "docker rmi <id>           # 删除镜像\n"
                    "```\n\n"
                    "## Docker Compose\n"
                    "```yaml\n"
                    "version: '3'\n"
                    "services:\n"
                    "  web:\n"
                    "    build: .\n"
                    "    ports:\n"
                    "      - '8000:8000'\n"
                    "```\n\n"
                    "## 清理\n"
                    "```bash\n"
                    "docker system prune -a    # 清理所有未使用资源\n"
                    "```"
                ),
                "tag_names": ["DevOps"],
            },
            {
                "title": "PostgreSQL 查询优化",
                "content_md": (
                    "# PostgreSQL 查询优化\n\n"
                    "## EXPLAIN ANALYZE\n"
                    "```sql\n"
                    "EXPLAIN ANALYZE\n"
                    "SELECT * FROM notes\n"
                    "WHERE user_id = 1\n"
                    "ORDER BY created_at DESC\n"
                    "LIMIT 20;\n"
                    "```\n\n"
                    "## 常用索引策略\n"
                    "1. **B-Tree** — 等值 + 范围查询\n"
                    "2. **GIN** — 全文搜索、JSONB\n"
                    "3. **Partial Index** — 部分索引减体积\n"
                    "4. **Covering Index** — INCLUDE 列避免回表\n\n"
                    "## 性能调优参数\n"
                    "- `shared_buffers` — 25% 内存\n"
                    "- `effective_cache_size` — 75% 内存\n"
                    "- `work_mem` — 排序/哈希内存\n"
                    "- `random_page_cost` — SSD 设为 1.1\n\n"
                    "> 慢查询日志：`log_min_duration_statement = 1000`"
                ),
                "tag_names": ["数据库"],
            },
            {
                "title": "Git 工作流规范",
                "content_md": (
                    "# Git 工作流规范\n\n"
                    "## 分支策略\n"
                    "```\n"
                    "main ← 生产就绪\n"
                    "  └── develop ← 集成分支\n"
                    "        ├── feature/xxx\n"
                    "        ├── bugfix/xxx\n"
                    "        └── hotfix/xxx\n"
                    "```\n\n"
                    "## Commit 规范\n"
                    "```\n"
                    "<type>: <subject>\n\n"
                    "<body>\n\n"
                    "<footer>\n"
                    "```\n\n"
                    "**类型**: feat | fix | docs | refactor | test | chore\n\n"
                    "## 示例\n"
                    "```\n"
                    "feat: 添加用户登录功能\n\n"
                    "- POST /api/auth/login\n"
                    "- JWT token 签发与校验\n"
                    "- 密码 bcrypt 哈希存储\n\n"
                    "Closes #42\n"
                    "```\n\n"
                    "## Code Review 要点\n"
                    "- 逻辑是否正确\n"
                    "- 是否有测试\n"
                    "- 命名是否清晰\n"
                    "- 是否有潜在性能问题"
                ),
                "tag_names": ["DevOps", "项目"],
            },
            {
                "title": "MySQL vs PostgreSQL 选型对比",
                "content_md": (
                    "# MySQL vs PostgreSQL\n\n"
                    "## 概览\n\n"
                    "| 特性 | MySQL | PostgreSQL |\n"
                    "|------|-------|------------|\n"
                    "| ACID | ✅ | ✅ |\n"
                    "| JSON | ✅ | ✅ (JSONB) |\n"
                    "| 全文搜索 | ✅ | ✅ (更强) |\n"
                    "| 窗口函数 | ✅ (8.0+) | ✅ |\n"
                    "| CTE | ✅ (8.0+) | ✅ |\n"
                    "| 地理空间 | ✅ | ✅ (PostGIS) |\n\n"
                    "## 何时选 MySQL\n"
                    "- 简单 CRUD 为主\n"
                    "- 读多写少\n"
                    "- 需要简单复制\n\n"
                    "## 何时选 PostgreSQL\n"
                    "- 复杂查询需求\n"
                    "- 数据完整性要求高\n"
                    "- 需要扩展（PostGIS、全文搜索）\n"
                    "- JSONB 灵活查询\n\n"
                    "> MVP 用 SQLite，未来按需迁移。"
                ),
                "tag_names": ["数据库"],
            },
        ],
    },
]


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _hash(plain: str) -> str:
    """对明文密码做 Unicode NFKC 归一化 → utf-8 → bcrypt 哈希。"""
    import unicodedata
    normalized = unicodedata.normalize("NFKC", plain)
    return bcrypt.hashpw(
        normalized.encode("utf-8"),
        bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS),
    ).decode("utf-8")


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

def seed_demo_data(db: Session) -> None:
    """幂等：如果 demo 用户已存在则跳过全部种子数据。"""
    existing = db.query(User).filter(User.username == "demo").first()
    if existing:
        return

    for user_def in _DEMO_USERS:
        # ── 创建用户 ──
        user = User(
            username=user_def["username"],
            email=user_def["email"],
            password_hash=_hash(user_def["password"]),
            is_demo=user_def["is_demo"],
        )
        db.add(user)
        db.flush()  # 获取 user.id

        # ── 创建标签 ──
        tag_map: dict[str, Tag] = {}
        for tag_name in user_def["tags"]:
            tag = Tag(name=tag_name, user_id=user.id)
            db.add(tag)
            db.flush()
            tag_map[tag_name] = tag

        # ── 创建笔记 + 关联标签 ──
        for note_def in user_def["notes"]:
            note = Note(
                title=note_def["title"],
                content_md=note_def["content_md"],
                user_id=user.id,
            )
            db.add(note)
            db.flush()

            for tag_name in note_def.get("tag_names", []):
                tag = tag_map.get(tag_name)
                if tag:
                    nt = NoteTag(note_id=note.id, tag_id=tag.id)
                    db.add(nt)

        # ── 为 demo 用户创建一条示例分享链接 ──
        if user_def["username"] == "demo":
            first_note = (
                db.query(Note)
                .filter(Note.user_id == user.id)
                .order_by(Note.id)
                .first()
            )
            if first_note:
                share = ShareLink(
                    token=uuid4().hex,
                    note_id=first_note.id,
                    created_by=user.id,
                    expires_at=datetime.utcnow() + timedelta(days=30),
                    is_active=True,
                )
                db.add(share)

    db.commit()
