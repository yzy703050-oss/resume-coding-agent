# Coding Agent 面试速记卡

配合 `INTERVIEW_PREP.md` 使用。先掌握主线，不必背完整手册。

## 30 秒开场

> 这是一个基于 LangChain、LangGraph 的本地单智能体 ReAct Coding Agent，围绕代码读取、精确修改和测试形成动作—观察循环。我重点关注工具约束、分层上下文、统一事件与异常收尾。当前有百余项离线工程测试和脚本演示，真实 DeepSeek 自主修复效果尚未测评。

## 十个必须懂的点

1. **架构**：单 Agent ReAct，不是 React，不是多 Agent，也不是独立 Planner。
2. **图**：guard → prepare → decide → execute → observe → guard；finish/限制结束，格式错误反馈重试。
3. **框架**：LangGraph 管路由；LangChain 管模型/消息/tool binding；应用仍管执行安全与记忆。
4. **步骤**：一次模型决策算业务 step，多个节点不等于多个模型请求；瞬态数据必须清理。
5. **工具**：六个固定工具 + finish 协议；Pydantic schema 单一来源；参数再校验后执行。
6. **安全**：路径包含检查、命令前缀白名单、shell=False、超时；pytest 仍能执行任意仓库代码，不是沙箱。
7. **记忆**：Working/Episodic + 确定性摘要 + AST Repo Map + SQLite；没有向量 embedding。
8. **持久化**：extractor 只提候选，脱敏/策略/来源/去重后入库；引用存在不等于内容真实。
9. **事件**：canonical 一次生成，history/audit 独立投影；模型不依赖强截断审计日志重建历史。
10. **预算与评测**：报告 usage 后停止不是账单硬上限；scripted 通过不是自主模型成功，真实判题需外部 hidden tests。

## 五句不能夸大

- 不说真实成功率 100%、省了多少 token、做过 SWE-bench。
- 不说已支持跨进程恢复；没有启用 checkpointer。
- 不说所有项目知识都能自动准确提取；当前主要是 Run Summary。
- 不说 full 已证明更好；baseline 仍默认。
- 不说 completed 就是代码正确，也不说配置 secret 脱敏等于通用 DLP。

## 三个可讲案例

- 先脱敏再截断，避免 secret 前缀残留。
- 清理瞬态状态，防止格式错误后误执行旧工具动作。
- 根据实际 client 标记 scripted/live，避免离线报告冒充模型评测。

每个案例都按：问题 → 实现 → 测试 → 仍存在的限制。

## 必看的五组文件

1. `agent/graph.py`、`agent/runner.py`：画四种路由。
2. `models/langchain_client.py`、`models/tool_binding.py`：解释请求与单动作解析。
3. `tools/registry.py`、`tools/paths.py`、`execution/policy.py`：解释执行边界。
4. `events/projections.py`、`memory/promotion.py`、`memory/identity.py`：解释日志和记忆边界。
5. `tests/behavior/test_graph_runtime.py`、`docs/EVALUATION.md`：拿出证据，讲清未验证项。

以上源码路径相对于 `src/coding_agent/`，tests/docs 路径相对于仓库根目录。

## 两项目对比一句话

> 旅行助手侧重 Plan-and-Execute 的业务协作和政策向量检索；Coding Agent 侧重 ReAct 的工具反馈、执行约束与可验证性，体现业务应用与 runtime 工程两种能力。

## 面试前自测

不看材料画图；90 秒讲完项目；解释 shell=False 不是沙箱；解释来源验证不是事实验证；设计一组不会被 Agent 改坏的 hidden tests。五项都能做到，再考虑补充框架术语。
