# 笔记管理系统 运行手册

> **版本**: 0.0.1 · **最后更新**: 2026-06-19

## 本地安装与启动

### 前置条件

- Python 3.10+
- conda 环境（推荐复用 `~/外部需求/.conda/codingagent`）

### 依赖安装

```bash
# 激活 conda 环境
conda activate ~/外部需求/.conda/codingagent

# 安装 Python 依赖
pip install fastapi uvicorn sqlalchemy bcrypt python-jose pydantic-settings

# 安装测试依赖
pip install pytest httpx
```

### 环境变量

在项目根目录创建 `.env` 文件（已 gitignored）：

```bash
# 数据库路径（相对于项目根目录 或 绝对路径）
DB_PATH=data/note_manager.db

# JWT 签名密钥（生产环境必须替换为强随机值）
JWT_SECRET=dev-secret-change-in-production

# 应用挂载路径前缀
BASE_PATH=/projects/note-manager

# 启动时是否填充演示数据（首次启动设为 true）
SEED_DEMO=true
```

### 启动命令

```bash
# 从项目根目录
cd src && uvicorn note_manager.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：
- SPA 首页: http://localhost:8000/projects/note-manager/
- 健康检查: http://localhost:8000/projects/note-manager/healthz

### 演示账号

启用 `SEED_DEMO=true` 后首次启动自动创建：
- 用户名: `demo`
- 密码: `demo123`

---

## 测试、构建与健康检查

### 运行全部测试

```bash
cd src && python -m pytest ../tests/ -v
```

### 运行特定模块

```bash
cd src && python -m pytest ../tests/ -v -k auth      # 认证测试
cd src && python -m pytest ../tests/ -v -k notes     # 笔记测试
cd src && python -m pytest ../tests/ -v -k tags      # 标签测试
cd src && python -m pytest ../tests/ -v -k shares    # 分享测试
cd src && python -m pytest ../tests/ -v -k edge      # 边界测试
```

### 带详细输出

```bash
cd src && python -m pytest ../tests/ -v -s           # 显示 print 输出
cd src && python -m pytest ../tests/ -v --tb=short   # 短回溯
```

### 健康检查

```bash
# 基本健康探针
curl http://localhost:8000/projects/note-manager/healthz
# 预期响应: {"status":"ok"}

# SPA Shell 正常返回 HTML
curl -I http://localhost:8000/projects/note-manager/
# 预期: HTTP/1.1 200 OK, Content-Type: text/html, Cache-Control: no-cache

# 静态资源可访问
curl -I "http://localhost:8000/projects/note-manager/static/css/app.css?v=0.0.1"
# 预期: HTTP/1.1 200 OK, Content-Type: text/css

curl -I "http://localhost:8000/projects/note-manager/static/js/app.js?v=0.0.1"
# 预期: HTTP/1.1 200 OK, Content-Type: application/javascript

# API 认证测试
curl -X POST http://localhost:8000/projects/note-manager/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"test123"}'
# 预期: 201 + user JSON
```

### 公网浏览器验收流程

1. 启动 uvicorn（`--host 0.0.0.0`）
2. 注册新用户 → 确认跳转登录
3. 登录 → 进入笔记列表（空状态引导）
4. 创建笔记 → Markdown 编辑器左栏输入，右栏实时预览
5. 保存 → 列表页出现新卡片
6. 搜索 → 输入关键词过滤笔记
7. 标签 → 添加/筛选/移除标签
8. 分享 → 生成链接，新标签页打开 → 只读 Markdown 渲染
9. 检查控制台无 JS 错误
10. 静态资源 URL 均带 `?v=0.0.1` 且在 `/projects/note-manager/` 路径下

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PATH` | `data/note_manager.db` | SQLite 数据库文件路径（相对项目根或绝对路径） |
| `JWT_SECRET` | `dev-secret-change-in-production` | JWT HS256 签名密钥，生产环境必须替换 |
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `JWT_EXPIRATION_HOURS` | `24` | Token 有效期（小时） |
| `BCRYPT_ROUNDS` | `12` | bcrypt 哈希轮次 |
| `BASE_PATH` | `/projects/note-manager` | 应用挂载路径前缀 |
| `SEED_DEMO` | `false` | 启动时是否填充演示数据（`demo/demo123`） |

环境变量通过 `.env` 文件或 shell 环境变量设置，由 `pydantic-settings` 自动加载。

---

## Base Path

项目强制使用 `/projects/note-manager/` 作为 URL 前缀：

- 所有 API 路径: `/projects/note-manager/api/...`
- 静态资源: `/projects/note-manager/static/...`
- SPA 壳页面: `/projects/note-manager/`
- 前端路由: `#/login`, `#/notes`, `#/notes/{id}`, `#/share/{token}`

**不得假设部署在 `/`**：前端 JS 中 API 调用、静态资源引用均使用 `BASE_PATH` 常量拼接完整路径（由 `index.html` 中的 `<meta name="base-path">` 注入，JS 读取 `document.querySelector('meta[name="base-path"]').content`）。

如需修改前缀，只需更改 `BASE_PATH` 环境变量，无需改动代码。

---

## 缓存策略

功能迭代后公网 URL 不变，必须防止浏览器缓存命中旧页面：

### HTML 文档（no-cache）

所有 `text/html` 响应由服务器中间件 `CacheControlMiddleware` 自动附加 HTTP 响应头：

```
Cache-Control: no-cache
```

**不得使用 `<meta http-equiv>` 标签代替**：浏览器基本忽略 `<meta>` 标签的缓存语义，必须由服务器/框架下发真实 HTTP 响应头。本项目通过 FastAPI 中间件实现（`src/note_manager/main.py:CacheControlMiddleware`）。

### 静态资源（版本令牌 + 长缓存）

所有 CSS/JS 文件 URL 携带版本令牌 `?v=0.0.1`：

```html
<link rel="stylesheet" href="/projects/note-manager/static/css/app.css?v=0.0.1">
<script src="/projects/note-manager/static/js/app.js?v=0.0.1"></script>
<script src="/projects/note-manager/static/js/marked.min.js?v=0.0.1"></script>
```

- 版本令牌随 `0.0.N` 递增，每个交付版本自动触发缓存失效
- 静态资源响应可设置长缓存：`Cache-Control: public, max-age=31536000`

### 验收检查清单

- [ ] HTML 响应头包含 `Cache-Control: no-cache`（`curl -I` 验证）
- [ ] 静态资源 URL 含 `?v=0.0.1` 令牌
- [ ] 静态资源路径在 `/projects/note-manager/` 前缀下
- [ ] 版本迭代时令牌随 `0.0.N` 更新

---

## Aliyun systemd 与 Nginx

### systemd 服务（0.0.1 参考，不部署）

```ini
# /etc/systemd/system/note-manager.service
[Unit]
Description=Note Manager 0.0.1
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/note-manager/src
EnvironmentFile=/opt/note-manager/.env
ExecStart=/opt/conda/envs/codingagent/bin/uvicorn note_manager.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Nginx 反向代理（0.0.1 参考，不部署）

```nginx
server {
    listen 80;
    server_name notes.example.com;

    location /projects/note-manager/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 日志查看

```bash
# 开发模式 — uvicorn 自带彩色日志输出到 stdout
cd src && uvicorn note_manager.main:app --host 0.0.0.0 --port 8000 --reload

# 生产模式 — 重定向到文件
cd src && uvicorn note_manager.main:app --host 0.0.0.0 --port 8000 2>&1 | tee app.log
```

uvicorn 日志格式：`<date> <level>: <message>`，包含请求方法、路径、状态码、耗时。

---

## 常见故障与恢复

### 1. SQLite 数据库被锁定 (database is locked)

**症状**: 请求返回 500，日志显示 `OperationalError: database is locked`

**原因**: 多进程同时写入或未提交的事务持有写锁

**恢复**:
```bash
# 1. 确认 WAL 模式已启用（main.py 启动时自动设置）
# 2. 检查是否有僵尸进程持有数据库连接
lsof data/note_manager.db
# 3. 重启 uvicorn
```

**预防**: WAL 模式允许并发读，但写操作仍串行。避免长时间运行的事务。

### 2. 端口已被占用 (Address already in use)

**症状**: `ERROR: [Errno 48] Address already in use`

**恢复**:
```bash
# 查找占用端口的进程
lsof -i :8000
# 杀死进程
kill -9 <PID>
# 或换端口启动
uvicorn note_manager.main:app --port 8001
```

### 3. JWT Secret 不匹配 (token 验证失败)

**症状**: 所有认证请求返回 401，即使凭据正确

**原因**: `.env` 中的 `JWT_SECRET` 与签发 token 时使用的 secret 不同（如重启后改了 secret 值）

**恢复**:
```bash
# 1. 确认 .env 中的 JWT_SECRET 值
# 2. 让用户重新登录获取新 token
# 3. 或清除 localStorage token 重新登录
```

### 4. 数据库文件权限错误

**症状**: `OperationalError: unable to open database file`

**恢复**:
```bash
# 检查 DB_PATH 指向的目录是否存在且可写
ls -la data/
# 确保父目录存在
mkdir -p data
# 检查文件权限
chmod 644 data/note_manager.db
```

### 5. 依赖缺失

**症状**: `ModuleNotFoundError: No module named 'xxx'`

**恢复**:
```bash
pip install fastapi uvicorn sqlalchemy bcrypt python-jose pydantic-settings pytest httpx
```

### 6. 种子数据问题

**症状**: 启动时种子数据报错

**恢复**: 种子数据是幂等的（检查是否已存在），重新启动即可。如需强制重建：
```bash
# 删除数据库文件
rm -f data/note_manager.db
# 确保 SEED_DEMO=true
export SEED_DEMO=true
# 重新启动
```

---

## 回滚到精确 Tag

```bash
# 查看 tag 列表
git tag -l

# 查看当前分支
git branch

# 当前迭代分支: iteration/0.0.1
# 主分支: main
# 注意: 0.0.1 迭代不进行 merge/tag/deploy，回滚只需 checkout 到目标 commit
git log --oneline -20
git checkout <commit-hash>
```
