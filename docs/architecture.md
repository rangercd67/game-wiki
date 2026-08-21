# 架构与安全边界

## 数据流

`E:\Games\GameTools` → 只读元数据扫描 → `data/local/index.sqlite3` → 本地 API → 浏览器界面。

- 索引器只调用目录枚举与文件 `stat`，不打开文件内容。
- 白名单内的可执行文件、动态库与压缩包只保存元数据。
- 预览接口必须由用户针对单个索引记录触发；文本上限 2 MB，图片上限 30 MB。
- `.exe`、`.dll`、安装包、脚本、压缩包、Office/PDF 等不通过内容接口提供，仅展示元数据。
- 源路径会经过索引存在性检查、规范化和根目录边界检查。

## 本地运行

```powershell
py -m gamewiki.indexer
py -m gamewiki.server
```

打开 `http://127.0.0.1:8765`。索引数据库是本地生成物，不提交到 Git。

## 既有成果

`legacy/jcwiki` 保存从 `jcwiki-main.zip` 导入的既有 GitHub 静态页面、资料与生成脚本。它们仅作历史成果管理，未接入主索引流程，也不会被主应用执行。
