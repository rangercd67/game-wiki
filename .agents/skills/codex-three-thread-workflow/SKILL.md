---
name: codex-three-thread-workflow
description: Coordinate complex Codex repository work with a decision-owning main thread, a bounded execution thread, and an independent verification thread. Use for long, noisy, risky, or parallelizable tasks; skip small, obvious, single-step edits.
---

# Codex 三线程交付

把需求决策、文件修改和独立验收放在不同逻辑线程中，避免主线程被探索记录、测试日志和排障过程淹没。这里的“线程”是职责上下文，不等于必须创建三个用户可见任务。

## 开始前

1. 完整阅读 [references/workflow.md](references/workflow.md)，再决定是否拆线程。
2. 读取适用的仓库规则，检查当前目录、Git 基线和未提交改动。
3. 先写清目标、范围、约束和可观察的验收标准；缺失信息只有在会实质改变结果时才向用户确认。
4. 小任务走单线程快速路径。三线程是风险控制手段，不是固定仪式。

## 不可破坏的不变量

- 主线程拥有目标、范围、优先级、争议决策和最终验收权。
- 同一个工作树同一时刻只有一个写入者。探索、日志分析和独立审查可以并行；重叠写入必须串行或使用隔离 worktree。
- 执行线程只能按任务简报改动，不得自行扩展范围、提交、推送或修改外部数据。
- 验证线程默认只读，必须检查候选结果本身，不能只复述执行线程的总结，也不能顺手修复发现的问题。
- `PASS_WITH_RISKS` 只能由主线程在现有授权内接受；越界写入、数据/权限边界破坏、用户工作丢失和未满足的必需验收项不能被风险接受替代。
- 文件、Git diff/提交、测试输出和可复现步骤是事实来源；聊天记忆不是。
- 交接只回传决策所需的摘要与证据，不把原始长日志倒回主线程。
- 内部委派使用 subagent。只有用户明确要求创建可见的新任务时，才创建侧边栏任务。

## 角色映射

优先使用项目 custom agents：

- `delivery_coordinator`：维护控制记录、安排顺序并作验收判断。
- `delivery_executor`：唯一写入者，实施并返回可复现证据。
- `delivery_verifier`：只读、独立验证并给出明确结论。

当运行时能选择或生成这些 agent 时优先使用；若名称不可选或 agent 工具不可用，用内置 worker/explorer、普通 subagent 或可复制的任务简报承担同一职责，但仍须遵守工作流中的交接契约和单写者规则。

## 完成条件

三线程路径只有在候选范围已冻结、相关检查有可复现结果、独立验证结论已处理、残余风险已明确后才能宣布完成。单线程快速路径由主线程担任唯一写入者并直接自检，不要求另开验证线程或执行完整交接。最终回复至少列出结果、改动文件、验证证据、未验证项或残余风险。
