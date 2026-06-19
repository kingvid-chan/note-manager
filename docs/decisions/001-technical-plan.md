# ADR-001: 笔记管理系统 MVP 技术方案

**状态**: accepted  
**日期**: 2026-06-19  
**迭代**: 0.0.1  
**关联事件**: e000001, e000003

---

## 1. 技术栈选择与理由

| 层次 | 技术 | 版本 | 理由 |
|------|------|------|------|
| 运行时 | Python | 3.10+ | 复用 `~/外部需求/.conda/codingagent` 环境 |
| Web 框架 | FastAPI | 0.100+ | 异步高性能、自动 OpenAPI 生成、Pydantic 校验、依赖注入 |
| ORM | SQLAlchemy | 2.0+ | 声明式模型、迁移支持、SQLite 无缝切换 |
| 数据库 | SQLite | — | 零配置 MVP、单文件部署、后续可迁 PostgreSQL |
| 密码哈希 | bcrypt | 4.0+ | 行业标准、内置盐值、抗暴力破解 |
| 认证 | python-jose | 3.3+ | JWT 签发/校验、OAuth2 兼容 |
| 前端 | 原生 HTML/CSS/JS | — | 无框架依赖、SPA 路由、极简交付 |
| Markdown | marked.js | CDN latest | 浏览器端实时渲染、零后端依赖 |
| 测试 | pytest + httpx | 7+ | 标准测试框架、ASGI 异步测试客户端 |
| WSGI/ASGI | uvicorn | 0.20+ | 生产级 ASGI、热重载开发 |

**选型原则**: 最小依赖链、复用已有环境、MVP 快速交付、后续可平滑升级。

---

## 2. 数据模型

### 2.1 ER 图 (文本)

```
User 1 ──── N Note
User 1 ──── N Tag
User 1 ──── N ShareLink
Note 1 ──── N ShareLink
Note N ──── M Tag  (via NoteTag)
Note 1 ──── N ActivityLog
```

### 2.2 SQLAlchemy 模型

#### User

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_demo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # 关系
    notes: relationship["Note"] = relationship(back_populates="author")
    tags: relationship["Tag"] = relationship(back_populates="owner")
    share_links: relationship["ShareLink"] = relationship(back_populates="creator")
```

- `username`: 登录凭据，唯一索引
- `email`: 可选联系方式，唯一索引
- `password_hash`: bcrypt 哈希结果
- `is_demo`: 演示账号标记，用于预填假数据

#### Note

```python
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="Untitled")
    content_md: Mapped[str] = mapped_column(Text, default="")
    content_html: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_published: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # 关系
    author: relationship["User"] = relationship(back_populates="notes")
    tags: relationship["Tag"] = relationship(secondary="note_tags", back_populates="notes")
    share_links: relationship["ShareLink"] = relationship(back_populates="note")
```

- `content_md`: 用户输入的 Markdown 原文
- `content_html`: 后端预渲染（可选，MVP 由前端 marked.js 渲染）
- `user_id + created_at`: 联合索引用于列表排序分页

#### Tag

```python
class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 关系
    owner: relationship["User"] = relationship(back_populates="tags")
    notes: relationship["Note"] = relationship(secondary="note_tags", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
    )
```

- 标签按用户隔离，同用户下标签名唯一

#### NoteTag (多对多关联表)

```python
class NoteTag(Base):
    __tablename__ = "note_tags"

    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

#### ShareLink

```python
class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # 关系
    note: relationship["Note"] = relationship(back_populates="share_links")
    creator: relationship["User"] = relationship(back_populates="share_links")
```

- `token`: uuid4 hex，公开分享的唯一标识
- `expires_at`: NULL 表示永不过期
- `is_active`: 软删除，支持手动关闭分享

#### ActivityLog

```python
class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=True)
    target_id: Mapped[int] = mapped_column(nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), index=True)
```

- 审计日志，记录关键操作（注册、登录、笔记 CUD、分享创建/删除）

### 2.3 索引策略汇总

| 表 | 索引列 | 类型 | 用途 |
|----|--------|------|------|
| users | id | PK | 主键 |
| users | username | UNIQUE | 登录查询 |
| users | email | UNIQUE | 邮箱查重 |
| notes | id | PK | 主键 |
| notes | user_id | FK INDEX | 按用户查询笔记 |
| notes | user_id, created_at | COMPOSITE | 列表分页排序 |
| tags | id | PK | 主键 |
| tags | user_id, name | UNIQUE | 用户下标签唯一 + 查询 |
| note_tags | note_id, tag_id | COMPOSITE PK | M:N 关联 |
| share_links | id | PK | 主键 |
| share_links | token | UNIQUE | 公开链接查询 |
| share_links | note_id | FK INDEX | 按笔记查分享 |
| share_links | is_active | INDEX | 过滤有效分享 |
| activity_logs | id | PK | 主键 |
| activity_logs | user_id | FK INDEX | 按用户查日志 |
| activity_logs | action | INDEX | 按操作类型过滤 |
| activity_logs | created_at | INDEX | 时间范围查询 |

---

## 3. API 设计

**Base**: `/projects/note-manager/api`

### 3.1 认证机制

- 登录返回 JWT access token (HS256, `sub=user.id`, `exp=24h`)
- 前端存 `localStorage`，请求带 `Authorization: Bearer <token>`
- FastAPI `Depends(get_current_user)` 解析 JWT → 注入 `User` 对象
- 公开分享接口无需认证

### 3.2 端点清单

#### 认证 `/api/auth`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/register` | 否 | 用户注册 |
| POST | `/api/auth/login` | 否 | 登录获取 token |
| GET | `/api/auth/me` | 是 | 获取当前用户信息 |

**POST /api/auth/register**
```json
// Request
{"username": "alice", "email": "alice@example.com", "password": "secret123"}
// Response 201
{"id": 1, "username": "alice", "email": "alice@example.com", "created_at": "2026-06-19T..."}
// Error 409: username or email already exists
```

**POST /api/auth/login**
```json
// Request (application/x-www-form-urlencoded 或 JSON)
{"username": "alice", "password": "secret123"}
// Response 200
{"access_token": "eyJ...", "token_type": "bearer", "user": {"id": 1, "username": "alice"}}
// Error 401: invalid credentials
```

**GET /api/auth/me**
```json
// Response 200
{"id": 1, "username": "alice", "email": "alice@example.com", "created_at": "..."}
```

#### 笔记 `/api/notes`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/notes` | 是 | 列表（分页 + 搜索 + 标签筛选） |
| POST | `/api/notes` | 是 | 创建笔记 |
| GET | `/api/notes/{id}` | 是 | 详情 |
| PUT | `/api/notes/{id}` | 是 | 更新 |
| DELETE | `/api/notes/{id}` | 是 | 删除 |

**GET /api/notes**
```
Query: ?page=1&size=20&q=keyword&tag=tag1,tag2
```
```json
// Response 200
{
  "items": [
    {
      "id": 1, "title": "My Note", "content_md": "# Hello",
      "tags": [{"id": 1, "name": "work"}],
      "is_published": false,
      "created_at": "...", "updated_at": "..."
    }
  ],
  "total": 42,
  "page": 1,
  "size": 20
}
```

**POST /api/notes**
```json
// Request
{"title": "New Note", "content_md": "# Hello", "tag_ids": [1, 2]}
// Response 201
{"id": 1, "title": "New Note", ...}
```

**PUT /api/notes/{id}**
```json
// Request
{"title": "Updated", "content_md": "# Updated", "tag_ids": [1]}
// Response 200
{"id": 1, ...}
// Error 403: not owner; 404: not found
```

**DELETE /api/notes/{id}**
```
// Response 204
// Error 403: not owner; 404: not found
```

#### 标签 `/api/tags`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/tags` | 是 | 当前用户所有标签 |
| POST | `/api/tags` | 是 | 创建标签 |
| DELETE | `/api/tags/{id}` | 是 | 删除标签 |

**GET /api/tags**
```json
// Response 200
{"items": [{"id": 1, "name": "work", "note_count": 5}, ...]}
```

**POST /api/tags**
```json
// Request
{"name": "work"}
// Response 201
{"id": 1, "name": "work"}
// Error 409: duplicate tag name for user
```

#### 分享 `/api/notes/{id}/share`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/notes/{note_id}/share` | 是 | 创建分享链接 |
| GET | `/api/notes/{note_id}/shares` | 是 | 查看笔记的所有分享 |
| DELETE | `/api/shares/{share_id}` | 是 | 撤销分享 |

**POST /api/notes/{note_id}/share**
```json
// Request
{"expires_in_hours": 24}  // null = 永不过期
// Response 201
{
  "id": 1,
  "token": "a1b2c3d4...",
  "url": "/projects/note-manager/share/a1b2c3d4...",
  "expires_at": "2026-06-20T...",
  "created_at": "..."
}
```

#### 公开分享页 API `/api/public`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/public/notes/{token}` | 否 | 通过分享 token 获取笔记 |

**GET /api/public/notes/{token}**
```json
// Response 200
{
  "id": 1,
  "title": "Shared Note",
  "content_md": "# Hello",
  "content_html": "<h1>Hello</h1>",
  "author": {"username": "alice"},
  "created_at": "...",
  "updated_at": "..."
}
// Error 404: share not found, expired, or inactive
```

### 3.3 全局错误格式

```json
{
  "detail": "human-readable message",
  "code": "NOT_FOUND"
}
```

- 401: 未认证或 token 过期
- 403: 无权限（非笔记所有者）
- 404: 资源不存在或分享失效
- 409: 资源冲突（用户名/邮箱已存在）
- 422: 请求校验失败（Pydantic）

---

## 4. 前端路由与页面结构

### 4.1 SPA 架构

```
Base Path: /projects/note-manager/
```

| 路由 | 页面 | 需要认证 | 说明 |
|------|------|----------|------|
| `/projects/note-manager/` | 首页/重定向 | — | 已登录→笔记列表，未登录→登录页 |
| `/projects/note-manager/login` | 登录页 | 否 | 含演示账号入口 |
| `/projects/note-manager/register` | 注册页 | 否 | |
| `/projects/note-manager/notes` | 笔记列表 | 是 | 搜索 + 标签筛选 |
| `/projects/note-manager/notes/new` | 新建/编辑笔记 | 是 | Markdown 编辑器 + 实时预览 |
| `/projects/note-manager/notes/{id}` | 查看/编辑笔记 | 是 | 同一组件，owner 可见编辑模式 |
| `/projects/note-manager/share/{token}` | 公开分享页 | 否 | 只读 Markdown 渲染 |

### 4.2 SPA Router 实现

- 原生 JS 实现 `hashchange` 路由（`#/notes`, `#/login`），避免服务端路由配置
- 页面结构由 `/projects/note-manager/index.html` 提供 shell
- 前端根据 `window.location.hash` 切换视图

### 4.3 静态资源

- CSS: `/projects/note-manager/static/css/app.css?v=0.0.1`
- JS: `/projects/note-manager/static/js/app.js?v=0.0.1`
- JS lib: `/projects/note-manager/static/js/marked.min.js?v=0.0.1`
- 所有脚本/样式带版本令牌 `?v=0.0.1`

### 4.4 HTTP 响应头

- HTML 文档响应强制 `Cache-Control: no-cache`（服务器设置，非 `<meta>`）
- 静态资源响应 `Cache-Control: public, max-age=31536000`（带版本令牌，可长缓存）

---

## 5. 目录结构

```
note-manager/
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── runbook.md
│   ├── README.md
│   ├── decisions/
│   │   ├── .gitkeep
│   │   └── 001-technical-plan.md          ← 本文件
│   └── iterations/
│       ├── .gitkeep
│       └── 0.0.1.md
├── src/
│   └── note_manager/
│       ├── __init__.py
│       ├── main.py                        # FastAPI app 创建 + 生命周期 + 中间件
│       ├── config.py                      # 配置（DB URL、JWT_SECRET、base_path 等）
│       ├── database.py                    # engine + sessionmaker + get_db 依赖
│       ├── models/
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── note.py
│       │   ├── tag.py
│       │   ├── share_link.py
│       │   └── activity_log.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── auth.py                    # 请求/响应 schema
│       │   ├── note.py
│       │   ├── tag.py
│       │   └── share.py
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   ├── notes.py
│       │   ├── tags.py
│       │   ├── shares.py
│       │   └── public.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── auth_service.py            # bcrypt 密码、JWT 签发
│       │   ├── note_service.py
│       │   ├── tag_service.py
│       │   └── share_service.py
│       ├── dependencies.py                # get_current_user 等 FastAPI 依赖
│       └── seed.py                        # 演示账号 + 假数据初始化
├── static/
│   ├── css/
│   │   └── app.css
│   └── js/
│       ├── app.js                         # SPA Router + API Client
│       └── marked.min.js                  # Markdown 渲染库
├── templates/
│   └── index.html                         # SPA shell (Cache-Control 由此下发)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                        # pytest fixtures (test client, test db)
│   ├── test_auth.py
│   ├── test_notes.py
│   ├── test_tags.py
│   └── test_shares.py
├── evidence/
│   └── claude/
│       └── .gitkeep
├── case/                                  # Hermes 管理，禁止手动修改
└── process-log/                           # gitignored
```

---

## 6. 安全设计

### 6.1 密码存储

- bcrypt 哈希，rounds=12
- 注册/登录时原文仅在内存中，不落盘不记录日志
- 数据库仅存 `password_hash`

### 6.2 JWT 会话

- 算法 HS256，secret 来自环境变量 `JWT_SECRET`（开发默认 `dev-secret`）
- Token 荷载: `{"sub": "<user_id>", "exp": <Unix timestamp>}`
- 过期时间 24 小时
- 无刷新 token（MVP 简化），过期后重新登录

### 6.3 分享链接

- token 使用 `uuid4().hex` (32 字符)，不可预测
- 支持过期时间，服务端校验 `expires_at` 和 `is_active`
- 分享页面只读，无编辑入口
- 不暴露笔记所有者邮箱等敏感信息

### 6.4 权限控制

- 所有 `/api/notes/*`、`/api/tags/*`、`/api/notes/*/share` 需要认证
- 笔记/标签/分享的操作者必须与 `user_id` 匹配
- 中间件 `get_current_user` 在每个请求中校验 token 有效性

### 6.5 其他

- SQLite 文件放在项目目录外（由 `DB_PATH` 配置），不随代码提交
- CORS: 生产环境仅允许同源（MVP 同域部署）
- 输入校验: Pydantic models，防 XSS（marked.js do not parse HTML by default）
- 敏感配置（JWT_SECRET、DB_PATH）从环境变量读取，`.env` 已 gitignored

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| SQLite 并发写瓶颈 | 多用户同时写入时性能下降 | MVP 阶段用户量极小；SQLite WAL 模式提升并发读；架构预留了 PostgreSQL 迁移路径（仅改 connection string） |
| JWT 无状态无法主动失效 | 用户无法"登出"已有的 token | MVP 可接受；后续可引入 token 黑名单或短 TTL + refresh |
| SPA hash 路由 SEO 不友好 | 搜索引擎不索引 | 笔记系统无需 SEO；如需后续可切 History API |
| 公开分享链接可被猜测 | 未授权访问 | uuid4 搜索空间 2^122，暴力不可行；支持过期和手动关闭 |
| `marked.js` CDN 不可用 | Markdown 渲染失败 | 本地托管 `marked.min.js`（放入 static/js/），不依赖 CDN |

---

## 8. 自测策略

### 8.1 测试覆盖目标

- **认证流程**: 注册、登录、token 校验、过期、错误密码
- **笔记 CRUD**: 创建、列表、详情、更新、删除、权限校验（非 owner 403）
- **标签**: 创建、列表、关联笔记、删除
- **分享**: 创建、公开访问、过期、撤销、404
- **边界**: 空标题、超长内容、特殊字符、并发请求

### 8.2 测试基础设施

```python
# conftest.py 核心 fixtures
@pytest.fixture
def client():
    # 创建内存 SQLite 数据库
    # override get_db 依赖
    # yield TestClient(app)

@pytest.fixture
def auth_headers(client):
    # 注册 testuser → 登录 → 返回 {"Authorization": "Bearer <token>"}
```

### 8.3 测试命令

```bash
cd src && python -m pytest ../tests/ -v
```

### 8.4 自测检查清单（Claude 编码完成后逐项确认）

- [ ] `pytest` 全部通过，无 skip
- [ ] 手动启动 `uvicorn`，`curl /projects/note-manager/healthz` 返回 200
- [ ] `curl /projects/note-manager/` 返回 HTML 且响应头包含 `Cache-Control: no-cache`
- [ ] `curl /projects/note-manager/static/css/app.css?v=0.0.1` 返回 200
- [ ] 浏览器访问注册→登录→创建笔记→编辑→搜索→标签→分享→公开查看完整流程
- [ ] 检查页面控制台无 JS 错误，静态资源路径均带 `?v=0.0.1`
- [ ] 所有自测通过后，将 `ready_for_verification = true` 写入 evidence
