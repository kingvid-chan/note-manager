# 笔记管理系统 当前架构

> **迭代**: 0.0.1 · **最后更新**: 2026-06-19 · **关联 ADR**: [ADR-001](decisions/001-technical-plan.md)

## 系统目标与边界

### 目标

笔记管理系统是一个单用户多笔记的 Markdown 知识管理工具。0.0.1 迭代交付完整 MVP：

- 用户注册与登录（含演示账号）
- 笔记增删改查、全文搜索、标签分类筛选
- Markdown 实时编辑预览（marked.js 浏览器端渲染）
- 公开分享链接（token 方式，支持过期时间，无需登录查看）

### 边界内

| 领域 | 涵盖 |
|------|------|
| 用户模型 | 注册、JWT 登录、Session 持久化（localStorage） |
| 笔记管理 | CRUD、分页列表、标题/正文 ILIKE 全文搜索、多标签 AND 筛选 |
| 标签系统 | 按用户隔离、自动创建（get_or_create）、使用计数 |
| 分享 | uuid4 token、过期时间、软撤销（is_active）、公开只读接口 |
| 前端 | 原生 HTML/CSS/JS SPA、hashchange 路由、marked.js 渲染 |
| 审计 | ActivityLog 记录关键操作（注册/登录/笔记 CUD/分享创建撤销） |
| 测试 | pytest + httpx + 内存 SQLite，覆盖认证/CRUD/标签/分享/边界 |

### 边界外（明确不做）

- OAuth / 第三方登录
- 多用户协作 / 团队空间
- 版本历史 / 笔记 diff
- 移动端 App / PWA
- 真实合同数据 / 批量导入
- OpenAPI 文档公开（docs_url=None, redoc_url=None）

---

## 技术栈与选择理由

| 层次 | 技术 | 版本 | 选择理由 |
|------|------|------|----------|
| 运行时 | Python | 3.10+ | 复用 `~/外部需求/.conda/codingagent` 环境，团队熟悉 |
| Web 框架 | FastAPI | 0.100+ | 异步高性能、自动 Pydantic 校验、依赖注入、轻量 |
| ORM | SQLAlchemy | 2.0+ | 声明式模型、session 管理、SQLite/PostgreSQL 无缝切换 |
| 数据库 | SQLite (WAL) | — | 零配置 MVP、单文件部署、WAL 模式提升并发读 |
| 密码哈希 | bcrypt | 4.0+ | 行业标准、内置 salt、抗暴力破解 |
| 认证 | python-jose | 3.3+ | JWT HS256 签发/校验、OAuth2 兼容 |
| 前端 | 原生 HTML/CSS/JS | — | 零框架依赖、SPA hashchange 路由、极简交付 |
| Markdown | marked.js | CDN latest (本地托管) | 浏览器端 GFM 渲染、sanitize 安全模式 |
| 测试 | pytest + httpx | 7+ | 标准框架、ASGI TestClient、内存 SQLite 隔离 |
| ASGI 服务器 | uvicorn | 0.20+ | 生产级 ASGI、热重载开发 |

**选型原则**: 最小依赖链 → 复用已有环境 → MVP 快速交付 → 架构预留 PostgreSQL 迁移路径（仅改 connection string）。

---

## 模块职责与依赖

### 目录结构

```
note-manager/
├── docs/
│   ├── architecture.md          ← 本文件
│   ├── runbook.md               # 运行手册
│   ├── README.md
│   ├── decisions/
│   │   └── 001-technical-plan.md  # ADR-001 技术决策
│   └── iterations/
│       ├── 0.0.1.md             # 迭代范围定义
│       └── 0.0.1-tasks.md       # 任务拆解 (T001–T023)
├── src/note_manager/
│   ├── main.py                  # FastAPI app 创建 + 生命周期 + 中间件 + 路由挂载
│   ├── config.py                # 配置 (DB_PATH, JWT_SECRET, BASE_PATH, SEED_DEMO)
│   ├── database.py              # engine + sessionmaker + get_db 依赖
│   ├── dependencies.py          # get_current_user (JWT 解析 + DB 查询)
│   ├── seed.py                  # 演示账号 + 假数据初始化
│   ├── models/
│   │   ├── user.py              # User 模型
│   │   ├── note.py              # Note 模型
│   │   ├── tag.py               # Tag + NoteTag 模型
│   │   ├── share_link.py        # ShareLink 模型
│   │   └── activity_log.py      # ActivityLog 审计模型
│   ├── schemas/
│   │   ├── auth.py              # 认证请求/响应 Pydantic schema
│   │   ├── note.py              # 笔记请求/响应 schema (含 TagBrief)
│   │   ├── tag.py               # 标签请求/响应 schema
│   │   └── share.py             # 分享请求/响应 schema
│   ├── routers/
│   │   ├── auth.py              # POST /api/auth/register, /login, GET /me
│   │   ├── notes.py             # 笔记 CRUD API (GET/POST/PUT/DELETE)
│   │   ├── tags.py              # 标签 API (列表/添加/移除关联)
│   │   ├── shares.py            # 分享 API (创建/列表/撤销)
│   │   └── public.py            # 公开分享查看 API (GET /api/public/notes/{token})
│   └── services/
│       ├── auth_service.py      # bcrypt 哈希校验 + JWT 签发/解析
│       ├── note_service.py      # 笔记 CRUD 业务逻辑 + 标签同步 + 审计
│       ├── tag_service.py       # 标签 CRUD + 笔记关联 + 使用计数
│       └── share_service.py     # 分享创建/撤销 + 审计
├── templates/
│   └── index.html               # SPA shell (含 CSS 变量系统 + 嵌套路由模板)
├── static/
│   ├── css/app.css              # 响应式 CSS 组件
│   └── js/
│       ├── app.js               # SPA Router + API Client + 全部视图组件
│       └── marked.min.js        # Markdown 渲染库 (本地托管, 非 CDN)
├── tests/
│   ├── conftest.py              # pytest fixtures: engine/client/auth_headers (+db/factories)
│   ├── factories.py             # 测试数据工厂 (create_test_user/note/tag/share)
│   ├── test_auth.py             # 认证服务层单元测试 + API 端点测试
│   ├── test_models.py           # SQLAlchemy 模型单元测试
│   ├── test_notes_api.py        # 笔记 CRUD API 集成测试
│   ├── test_tags_api.py         # 标签 API 集成测试
│   ├── test_tags.py             # 标签模块测试 (create/duplicate/list/delete/not_owner)
│   ├── test_shares_api.py       # 分享 API 集成测试
│   ├── test_shares.py           # 分享模块测试 (含过期 token 测试)
│   ├── test_edge_cases.py       # 边界 & 安全测试
│   └── test_frontend.py         # 前端集成测试
└── evidence/claude/
    └── handoff-0.0.1.json       # 自测证据 & 交付状态
```

### 模块依赖图

```
config.py ─────────────────────────────────────────────┐
    │                                                   │
database.py ──→ models/ ──→ services/ ──→ routers/ ──→ main.py
    │               │           │            │
dependencies.py ────┘           │            │
    │                           │            │
schemas/ ←──────────────────────┘            │
    │                                        │
templates/ ──→ static/ ──────────────────────┘
```

- `main.py`: 组装入口，挂载中间件 → 路由 → 静态文件 → 生命周期
- `routers/`: 薄层，仅负责 HTTP 请求/响应映射，调用 services，返回 Pydantic schema
- `services/`: 纯 SQLAlchemy 业务逻辑，不依赖 FastAPI，可独立单元测试
- `models/`: SQLAlchemy 2.0 Mapped 声明式模型，定义表结构与关系
- `schemas/`: Pydantic v2 请求校验与响应序列化
- `database.py`: engine（WAL 模式）+ sessionmaker + get_db 依赖生成器
- `dependencies.py`: get_current_user FastAPI 依赖（JWT → DB 查询 → 注入 User）
- `config.py`: pydantic-settings 从环境变量/.env 读取配置

---

## 数据流、状态流与外部接口

### 请求生命周期

```
Client (browser/curl)
    │
    ▼
CacheControlMiddleware   ← 对所有 text/html 响应附加 Cache-Control: no-cache
    │
    ▼
FastAPI Router           ← BASE_PATH=/projects/note-manager
    │
    ├── GET  /healthz                  → {"status": "ok"}
    ├── GET  /, /index.html            → templates/index.html (SPA shell)
    ├── POST /api/auth/register        → User 创建 + ActivityLog → 201
    ├── POST /api/auth/login           → JWT 签发 → 200 {access_token}
    ├── GET  /api/auth/me              → get_current_user → 200 User info
    ├── GET  /api/notes/?page&search   → note_service.list_notes → 200
    ├── POST /api/notes/               → note_service.create_note → 201
    ├── GET  /api/notes/{id}           → note_service.get_note → 200/404
    ├── PUT  /api/notes/{id}           → note_service.update_note → 200/403/404
    ├── DELETE /api/notes/{id}         → note_service.delete_note → 204/403/404
    ├── GET  /api/tags/                → tag_service.list_user_tags → 200
    ├── POST /api/notes/{id}/tags      → tag_service.get_or_create + add → 201
    ├── DELETE /api/notes/{id}/tags/{tid} → tag_service.remove → 204
    ├── POST /api/notes/{id}/share     → share_service.create_share → 201
    ├── GET  /api/shares/              → share_service.list_user_shares → 200
    ├── DELETE /api/shares/{id}        → share_service.revoke_share → 204
    ├── GET  /api/public/notes/{token} → 公开只读 (无认证) → 200/404
    └── /static/*                       → StaticFiles (版本令牌长缓存)
```

### 认证数据流

```
1. POST /api/auth/login {username, password}
2. auth_service.verify_password(plain, hash) → OK
3. auth_service.create_access_token(user.id) → JWT (HS256, exp=24h)
4. 客户端存 localStorage.setItem("token", ...)
5. 后续请求: fetch(url, {headers: {"Authorization": "Bearer <token>"}})
6. dependencies.get_current_user:
   - 提取 Authorization header → Bearer token
   - auth_service.decode_access_token(token) → payload {"sub": user_id}
   - db.query(User).filter(User.id == user_id).first()
   - 注入 current_user: User 对象
```

### 前端 SPA 路由

```
Base URL: /projects/note-manager/
Router: hashchange (#/) 模式

#/login       → 登录页
#/register    → 注册页
#/notes       → 笔记列表（搜索 + 标签筛选 + 分页）
#/notes/new   → 新建笔记编辑器（Markdown + 实时预览）
#/notes/{id}  → 查看/编辑笔记
#/share/{token} → 公开分享只读页
```

### 外部依赖

| 依赖 | 用途 | 故障影响 |
|------|------|----------|
| SQLite 文件 | 数据持久化 | 应用不可用；恢复：检查 DB_PATH 路径权限 |
| marked.js (本地) | Markdown → HTML 渲染 | 前端预览失效（JS 报错）；已本地托管，不依赖 CDN |
| python-jose | JWT 签发/校验 | 认证完全不可用 |
| bcrypt | 密码哈希 | 无法注册/登录新用户 |

---

## 测试策略

### 测试层次

```
┌──────────────────────────────┐
│  test_frontend.py            │  ← 前端集成测试 (TestClient + CSS/JS class 检测)
│  test_edge_cases.py          │  ← 边界 & 安全测试
├──────────────────────────────┤
│  test_auth.py                │
│  test_notes_api.py           │  ← API 集成测试 (TestClient + 内存 SQLite)
│  test_tags.py / _api.py      │
│  test_shares.py / _api.py    │
├──────────────────────────────┤
│  test_auth.py (前半)          │  ← 服务层单元测试 (纯函数, 不依赖 FastAPI)
│  test_models.py              │  ← 模型单元测试 (SQLAlchemy 模型行为)
└──────────────────────────────┘
```

### 基础设施

- **数据库隔离**: 每个测试函数独立的 `sqlite:///:memory:` 数据库，`StaticPool` 确保所有连接指向同一内存库
- **认证 fixture**: `auth_headers` 自动注册 `testuser` 并返回 Bearer token
- **数据工厂**: `tests/factories.py` 提供 `create_test_user/note/tag/share` 工厂函数
- **依赖覆盖**: `client` fixture 通过 `app.dependency_overrides` 将 `get_db` 替换为内存数据库会话

### 覆盖目标

| 模块 | 测试文件 | 覆盖点 |
|------|----------|--------|
| 认证 | test_auth.py | 注册/登录/me、重复/无效/过期 token、form-urlencoded |
| 笔记 | test_notes_api.py | CRUD、分页、搜索(ILIKE)、标签筛选(AND)、所有权隔离 |
| 标签 | test_tags_api.py + test_tags.py | 创建/列表/重复/移除/所有权 |
| 分享 | test_shares_api.py + test_shares.py | 创建/过期/列表/撤销/公开访问/所有权 |
| 边界 | test_edge_cases.py | 超长输入、XSS 存储、SQL 注入安全、Unicode、并发 |
| 模型 | test_models.py | User/Note/Tag/ShareLink 模型行为验证 |
| 前端 | test_frontend.py | SPA shell、路由、API Client、HTML 结构 |

### 运行命令

```bash
cd src && python -m pytest ../tests/ -v          # 全部测试
cd src && python -m pytest ../tests/ -v -k auth  # 特定模块
```

---

## 部署拓扑

### 开发环境

```
┌──────────┐     ┌──────────────────────────────────┐
│ Browser  │────▶│ uvicorn (localhost:8000)          │
│ / Kimi   │    │   ├── FastAPI app                  │
└──────────┘     │   ├── SQLite (WAL, data/*.db)     │
                 │   ├── Static files (/static/)     │
                 │   └── Templates (/templates/)     │
                 └──────────────────────────────────┘
```

- **启动命令**: `cd src && uvicorn note_manager.main:app --host 0.0.0.0 --port 8000 --reload`
- **Base Path**: `/projects/note-manager/`（所有路由、静态资源在此前缀下）
- **数据库**: SQLite 文件路径由 `DB_PATH` 环境变量控制，默认 `data/note_manager.db`
- **并发模型**: 单进程 ASGI，SQLite WAL 模式支持多读单写

### 生产注意事项（0.0.1 不做）

- Nginx 反向代理：`proxy_pass http://127.0.0.1:8000`，`proxy_set_header X-Forwarded-Proto`
- systemd 服务：`Restart=always`，`WorkingDirectory=/opt/note-manager/src`
- 数据库备份：`sqlite3 data/note_manager.db ".backup 'backup.db'"`
- PostgreSQL 迁移：仅需修改 `DB_PATH` → PostgreSQL connection string

---

## 安全边界

### 纵深防御层次

```
┌───────────────────────────────────────┐
│ 1. 传输层                              │
│    - MVP 同域部署，无跨域需求           │
│    - 生产需 Nginx TLS 终端              │
├───────────────────────────────────────┤
│ 2. 认证层                              │
│    - JWT HS256, 24h TTL               │
│    - 所有 /api/* 端点需要 Bearer token │
│    - 公开接口 /api/public/* 无需认证    │
├───────────────────────────────────────┤
│ 3. 授权层                              │
│    - 笔记/标签/分享操作匹配 user_id    │
│    - 非 owner：返回 403 或 404(遮罩)   │
├───────────────────────────────────────┤
│ 4. 数据层                              │
│    - bcrypt 哈希 (rounds=12)          │
│    - Pydantic 输入校验 (长度/类型)     │
│    - SQLAlchemy 参数化查询 (防注入)    │
│    - 密码不落盘、不记录日志            │
│    - 响应不返回 password_hash          │
├───────────────────────────────────────┤
│ 5. 输出层                              │
│    - marked.js sanitize 模式           │
│    - 公开分享不暴露 email 等敏感字段   │
│    - 错误响应不泄露内部细节            │
└───────────────────────────────────────┘
```

### 密钥管理

| 配置项 | 来源 | 默认值 | 生产要求 |
|--------|------|--------|----------|
| JWT_SECRET | 环境变量 | `dev-secret-change-in-production` | 随机 256-bit，不可硬编码 |
| DB_PATH | 环境变量 | `data/note_manager.db` | 项目目录外路径 |
| BCRYPT_ROUNDS | 环境变量 | 12 | ≥12 |
| SEED_DEMO | 环境变量 | `false` | 生产必须为 `false` |
| BASE_PATH | 环境变量 | `/projects/note-manager` | 按部署路径配置 |

---

## 已知技术债

| # | 项目 | 影响 | 缓解 / 计划 |
|---|------|------|-------------|
| 1 | **SQLite 并发写瓶颈** | 多用户同时写入时性能下降 | MVP 用户量极小，不触发；WAL 模式提升并发读；架构预留 PostgreSQL 迁移（仅改 connection string） |
| 2 | **JWT 无状态无法主动失效** | 用户无法"登出"已有 token | MVP 可接受（24h TTL）；后续引入 token 黑名单或短 TTL + refresh token |
| 3 | **SPA hash 路由 SEO 不友好** | 搜索引擎不索引 | 笔记系统无需 SEO；后续可切 History API + SSR |
| 4 | **公开分享链接可被猜测** | 未授权访问 | uuid4 搜索空间 2^122，暴力不可行；支持过期时间 + 手动关闭（is_active=false） |
| 5 | **无 refresh token** | token 过期后需重新登录 | MVP 简化（24h TTL 够日常使用）；后续引入 |
| 6 | **datetime.utcnow() 废弃** | Python 3.12+ 警告 | 部分使用 `datetime.utcnow()`，后续迁移到 `datetime.now(datetime.UTC)` |
| 7 | **无数据库迁移工具** | Schema 变更需手动处理 | MVP 阶段表结构稳定，create_all 足够；后续引入 Alembic |

---

## 关联 ADR 与最近变更

### ADR

| ADR | 标题 | 状态 |
|-----|------|------|
| [ADR-001](decisions/001-technical-plan.md) | 笔记管理系统 MVP 技术方案 | accepted |

### 最近变更 (0.0.1)

| 阶段 | 任务 | 内容 |
|------|------|------|
| 后端基础 | T001–T005 | 项目骨架、数据模型、数据库初始化、认证服务层、认证 API |
| 核心 API | T006–T009 | 笔记 CRUD、标签、分享、公开查看 |
| 前端 | T010–T015 | SPA Shell、登录注册、笔记列表、编辑器、分享页、标签管理 |
| 测试 | T016–T020 | fixtures、认证/笔记/标签/分享 API 测试、数据工厂、边界用例 |
| 文档 | T021–T022 | architecture.md、runbook.md |
| 交付 | T023 | handoff-0.0.1.json |

### Git 分支

- 当前分支: `iteration/0.0.1`
- 主分支: `main`
- 不合并、不打 tag、不部署（按 CLAUDE.md 约束）
