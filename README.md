# Game Wiki · 藏经阁

面向本地游戏资料的只读 Wiki：按游戏分类、关键词搜索、元数据浏览，以及用户主动触发的单文件预览。

## 目录边界

- 工作目录：`D:\Development\Projects\game-wiki`
- 外部数据源：`E:\Games\GameTools`（只读引用，不纳入本仓库）

## 协作流程

1. Trae 进行小步开发。
2. 每个稳定节点进行一次可回滚的 Git 提交。
3. Codex 处理复杂任务或进行独立审查。
4. 敏感代码、凭据和私有数据在共享前脱敏。
5. 项目成熟后，在独立 worktree 中测试 DSH。
6. WorkBuddy 整理文档、周报和知识库。

## 快速开始

环境要求：Python 3.11 或更高版本，无第三方依赖。

```powershell
# 只枚举白名单文件并读取 stat 元数据，不读取正文
py -m gamewiki.indexer

# 启动仅监听本机的 Wiki
py -m gamewiki.server
```

浏览器访问 `http://127.0.0.1:8765`。默认数据源为 `E:\Games\GameTools`，索引写入仓库的 `data/local/`（已忽略）。

安全设计与自定义参数见 [docs/architecture.md](docs/architecture.md)。既有 GitHub 项目成果统一保存在 `legacy/jcwiki/`，不参与主程序执行。
