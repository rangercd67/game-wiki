# Game Wiki · 藏经阁

面向本地游戏资料的只读 Wiki：按游戏分类、关键词搜索、元数据浏览，以及用户主动触发的单文件预览。

## 目录边界

- 工作目录：`D:\Development\Projects\game-wiki`
- 资料库：`library/`——被索引的本地资料（攻略、图集等），**不纳入 Git**
- 历史外部源：`E:\Games\GameTools` 已不再参与索引，仅作个人归档保留

资料库是仓库内的普通目录，但被 `.gitignore` 排除：其中的攻略多为他人作品，且体积上百 MB，提交入库会让仓库永久膨胀。

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

浏览器访问 `http://127.0.0.1:8765`。默认数据源为仓库内的 `library/`，索引写入仓库的 `data/local/`（已忽略）。两者都可用 `--source` 与 `--database` 覆盖。

## 测试

```powershell
py -m unittest discover -s tests -t .
```

无需网络与第三方依赖。`tests/test_web_assets.py` 静态校验 `web/index.html` 与 `web/app.js` 之间的 id、class 选择器及资源引用是否自洽——重复 id 或选择器失配会让整块界面静默失效，这类问题无法靠后端测试发现。

安全设计与自定义参数见 [docs/architecture.md](docs/architecture.md)。既有 GitHub 项目成果统一保存在 `legacy/jcwiki/`，不参与主程序执行。
