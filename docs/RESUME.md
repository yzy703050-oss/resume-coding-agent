# 简历与面试展示

## 可直接使用的项目描述

**框架化 Coding Agent｜Python、LangChain、LangGraph、Pydantic、SQLite、pytest**

- 使用 LangGraph 状态图编排单智能体 ReAct 编码闭环，划分预算检查、上下文准备、模型决策、工具执行与结果观察节点，通过条件路由支持任务结束、失败恢复及预算停止。
- 设计分层上下文与项目记忆：Working/Episodic Memory、确定性有界历史摘要、Python AST Repo Map 和 SQLite 项目隔离存储；候选经过脱敏、策略、来源引用及去重校验后入库。
- 构建 12 任务 DeepSeek 真实模型评测，使用隔离仓库、外部 hidden tests 与干净副本判题验证代码补丁；单次完整协议评测通过 0/12，其中 6/12 补丁通过 hidden oracle，并基于完整失败轨迹定位 tool-call 格式与终止协议兼容问题。

不要写“真实成功率 100%”“节省 40% token”“完成 SWE-bench 测评”。本次真实评测严格成功数为 0/12，总 reported tokens 为 74,506；不能把 6/12 oracle-passing patches 改写成完整任务成功。若简历篇幅有限，建议保留“构建可信评测与定位兼容问题”的工程贡献，不单独宣传模型效果数字。框架依赖、默认运行路径和付费端到端链路均已实际接线，不是仅添加依赖。

## 与旅行助手一起展示

旅行助手强调业务侧的规划执行、外部信息获取和偏好记忆；Coding Agent 强调代码侧的工具边界、失败恢复、上下文取舍与工程可观测性。两个项目形成“业务应用 + Agent runtime 工程”的互补，不必再复制旅行项目的多 Agent、向量库或 Web UI。

## 重点理解顺序

1. `agent/graph.py` 和 `agent/runner.py`：为什么每步只有一个 action，条件边如何控制循环，agent step 与 graph step 有何区别，谁拥有 terminal event。
2. `events/recorder.py` 与 projections：一次生成事件事实，分别投影到 richer history 与 audit，correlation_id 保留因果关联。
3. `context/manager.py` 与 selector：上下文来源如何组合，为什么不是把所有历史塞给模型；字符预算与 token 预算的区别。
4. `memory/candidates.py`、promotion、persistent：extractor 只提议、不直接写库；project_id 的 remote/common-dir 规则；来源引用验证不等于事实真实性验证。
5. `evaluation/live.py`、`trusted_oracle.py` 和本目录评测文档：为什么 scripted 正确不能证明模型正确，如何用外部 hidden oracle 做可信判题，以及为何补丁正确但未 finish 仍不是完整成功。
6. `models/langchain_client.py` 与 `tool_binding.py`：LangChain 如何绑定原有工具契约，如何把 AIMessage 解码成单动作并映射 usage；为何不用框架默认 shell/tool memory 替代工程边界。

## 尚未完成，不应包装成现成功能

最终格式化 header/omission 字符精确计入上下文预算、最新事件的显式优先级及严格 section 配额、Repo Map symlink/ignored-file 防护、候选内容与 canonical evidence 的语义匹配、数据库失败诊断/生命周期、LLM auxiliary 失败计费和生产接线仍需后续 hardening。跨进程恢复和 full 默认化仍不在范围内。
