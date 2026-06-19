# 笔记管理系统 技术专家约束

1. 必读 `docs/architecture.md`、当前 `docs/iterations/0.0.N.md` 和相关 ADR。
2. 禁止直接修改 `case/`；项目状态由 Hermes 通过 casefile 工具记录。
3. 只在 `iteration/0.0.N` 分支实施，不合并 main、不打 tag、不部署。
4. 每项可验证改动一个小提交，不跳过 Git hooks。
5. 自测通过后只能申请 Hermes 独立验收，不得宣布交付。
6. 架构、运行方式或重要决策变化时同步更新 docs。
7. 开发权限由 Hermes 统一授权；不要向老板索要文件、命令或工具审批，遇到硬门禁时向 Hermes 提供非破坏性替代方案。
8. 静态资源 URL 必须带 `?v=<当前 0.0.N>` 版本令牌、HTML 文档必须由服务器下发真实 `Cache-Control: no-cache` **HTTP 响应头**（不能用 `<meta>` 标签代替），且资源路径保留 `/projects/note-manager/` 前缀；否则 Hermes 浏览器验收会拒。
