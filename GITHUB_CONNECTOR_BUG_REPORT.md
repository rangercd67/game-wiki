# 工单：GitHub 连接器（CodeBuddy-Connector）缺失 repo 作用域，代码协作能力全部不可用

> 提交前请整篇复制下方内容，粘贴到 WorkBuddy 的「意见反馈 / 提交工单」入口。

---

## 问题标题
【Bug】GitHub 连接器（CodeBuddy-Connector）缺失 `repo` 作用域，克隆/推送/管 PR 等代码协作能力全部失效，且描述与实际授权不符

## 环境信息
- 产品：WorkBuddy（CodeBuddy）
- 连接器：GitHub（App 内状态显示「已连接」）
- 实际授权对象：GitHub OAuth App **「CodeBuddy-Connector」**
- 登录账号：`rangercd67`
- 受影响仓库：`rangercd67/jcwiki`（私有仓库）

## 复现步骤
1. 在 WorkBuddy 中连接 GitHub 连接器并完成授权。
2. 调用 `get_me` → **成功**，返回账号信息（证明账号级授权是正常的）。
3. 调用 `get_file_contents` 读取私有仓库 `jcwiki` → **404 Not Found**。
4. 调用 `push_files` 向 `jcwiki` 推送文件 → **404 Not Found**。
5. 调用 `create_repository` 新建仓库 → **403 Resource not accessible by integration**。

## 根因分析
- 该连接器对应的 GitHub OAuth App「CodeBuddy-Connector」在授权页中**仅包含账号 / 资料 / 邮件 / Codespaces / 被关注仓库等元数据权限，未申请 `repo` 作用域**。
- OAuth App 的权限范围由 **App 所有者（WorkBuddy）在注册时固定**，终端用户无法在 GitHub 侧为其追加仓库读写权限：
  - GitHub 的「Authorized OAuth Apps」页面**没有**“授予某仓库访问”的开关（该开关仅 GitHub App / Installation 才有）。
  - 因此无论用户如何重连、如何在 GitHub 设置里操作，连接器都拿不到仓库读写能力。

## 矛盾点（文档与实现不符 · 重点）
- **连接器描述承诺**：「在 GitHub 上克隆、推送代码，查看和管理仓库与 Pull Request，用自然语言完成代码协作」。
- **实际行为**：因无 `repo` 权限，私有仓库既不可见也不可写，上述能力全部失效。
- 即：**描述（能力清单 / 规格）= 完整代码协作；实际授权（scope）= 仅元数据权限**。两者严重不符，对用户体验构成误导。

## 影响
- 已连接账号却无法对任何仓库（公开 / 私有）进行读写，广告中的代码协作功能形同虚设。
- 用户无法借助该连接器完成「上传项目到 GitHub 私有仓库」等真实需求，只能绕回本地 `git push`。

## 期望
- **方案 A（推荐）**：在「CodeBuddy-Connector」的 OAuth App 注册中增补 `repo`（及必要的 `read:org` / `workflow` 等）作用域，使连接器真正具备仓库读写与 PR 管理能力。
- **方案 B**：若短期内无法补全权限，请至少将连接器描述改为与实际授权一致，避免继续误导用户。

## 建议复验
补全权限后，用同一账号复测 `get_file_contents` / `push_files` / `create_repository`，应均返回成功（200 / 创建成功）。

## 附录：复现仓库
`rangercd67/jcwiki`（私有，当前连接器无权限访问，可作为复验目标）
